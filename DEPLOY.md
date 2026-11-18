# Deploying Mini Gauntlet on AWS

A design note, not a runbook: nothing here has been deployed.

## Runtime

| Concern | Choice | Why |
|---|---|---|
| Dashboard | Vite build in a private **S3** bucket behind **CloudFront** (Origin Access Control). A response headers policy sends the same CSP as `nginx.conf`. | Static files need no servers. |
| API | The same `backend/Dockerfile` image on **ECS Fargate**: 2+ tasks across two AZs behind an **ALB**. CloudFront routes `/api/*` to the ALB, so the dashboard keeps using relative URLs. | No hosts to patch. Rolling deploys use the existing `/api/health` check. |
| Scans | First version: unchanged (a background task inside the API task). Next step: `POST /api/scans` puts a message on **SQS** and a separate Fargate worker service runs the scan. | Then a deploy or scale-in can't kill a running scan. |
| Database | **RDS PostgreSQL**, Multi-AZ, encrypted, automated backups. SQLite only works with one task on one disk. The SQL in `db.py` is plain and ports with small changes (`?` → `%s`, `SERIAL`). | Several tasks need a shared database. |
| Auth | ALB authentication with **Cognito** or the company IdP (OIDC) in front of the API and dashboard. | The app has no login of its own. |

## Networking
- A VPC with public subnets that hold only the ALB (and NAT gateways), and private subnets for the Fargate tasks and RDS.
- Security groups chain each hop to the previous one: CloudFront managed prefix list → ALB :443 → API tasks :8000 → RDS :5432.
- Interface **VPC endpoints** for ECR, CloudWatch Logs, Secrets Manager and STS keep that traffic off the internet. NAT is only for calls to Azure and GCP APIs.

## Secrets
- The RDS master password is managed by RDS in **Secrets Manager** and injected through the ECS task definition's `secrets` block. It never goes into an image, environment file or git.
- AWS access comes from the **task role**, so there are no access keys. Azure and GCP access uses **workload identity federation**: an Entra ID federated credential and a GCP Workload Identity Pool that trust the task role's identity. No cloud keys are stored anywhere.

## Logs and monitoring
- Containers log to **CloudWatch Logs** through the `awslogs` driver, with 30-day retention. The scanner's CANNOT_SCAN warnings land there too.
- CloudWatch alarms watch ALB 5xx, unhealthy targets, RDS CPU and storage, and a metric filter on `Scan .* failed`.
- **CloudTrail** in the scanned accounts records every read the scanner makes.

## CI/CD without long-lived keys
1. The existing workflow lints, tests and builds both images on every push.
2. On `main`, a deploy job uses **GitHub OIDC** (`permissions: id-token: write`) with `aws-actions/configure-aws-credentials` to assume `GitHubDeployRole`. That role's trust policy accepts only `token.actions.githubusercontent.com` with `sub = repo:<org>/mini-gauntlet:ref:refs/heads/main`.
3. The role can only:
   - push to the two ECR repositories
   - `ecs:RegisterTaskDefinition` and `ecs:UpdateService` on the two services
   - `iam:PassRole` for the two task roles
   - `s3:PutObject` to the dashboard bucket and `cloudfront:CreateInvalidation`
4. Images are tagged with the git SHA and ECR is set to immutable tags. ECS rolls tasks over and rolls back if health checks fail.

## Read-only permissions for the ten checks

Each scanned AWS account gets a `MiniGauntletReadOnly` role. Its trust policy allows only the scanner's task role and requires an `sts:ExternalId` per customer. It has exactly this policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3PublicAccessBlock",
      "Effect": "Allow",
      "Action": ["s3:ListAllMyBuckets", "s3:GetBucketLocation", "s3:GetBucketPublicAccessBlock"],
      "Resource": "*"
    },
    { "Sid": "SecurityGroups", "Effect": "Allow",
      "Action": ["ec2:DescribeRegions", "ec2:DescribeSecurityGroups"], "Resource": "*" },
    { "Sid": "IamMfaAndKeys", "Effect": "Allow",
      "Action": ["iam:ListUsers", "iam:GetLoginProfile", "iam:ListMFADevices", "iam:ListAccessKeys"],
      "Resource": "*" },
    { "Sid": "Rds", "Effect": "Allow", "Action": ["rds:DescribeDBInstances"], "Resource": "*" }
  ]
}
```

| Check | AWS actions it needs |
|---|---|
| AWS-S3-01 | `s3:ListAllMyBuckets`, `s3:GetBucketLocation` (region), `s3:GetBucketPublicAccessBlock` |
| AWS-EC2-01 | `ec2:DescribeRegions`, `ec2:DescribeSecurityGroups` |
| AWS-IAM-01 | `iam:ListUsers`, `iam:GetLoginProfile` (console access), `iam:ListMFADevices` |
| AWS-IAM-02 | `iam:ListUsers`, `iam:ListAccessKeys` (status and creation date) |
| AWS-RDS-01 | `rds:DescribeDBInstances` (`PubliclyAccessible`) |

The managed `SecurityAudit` policy would also work, but it grants hundreds of reads this catalog doesn't need. A failed call (`AccessDenied`) shows up as the CANNOT_SCAN finding the scanner already emits.

The other five checks use the same idea in each cloud: a custom read-only role.

| Check | Azure custom role (subscription scope) | Google Cloud custom role (project scope) |
|---|---|---|
| AZ-STG-01 | `Microsoft.Storage/storageAccounts/read` (`allowBlobPublicAccess`) | - |
| AZ-NSG-01 | `Microsoft.Network/networkSecurityGroups/read` | - |
| GCP-GCS-01 | - | `storage.buckets.list`, `storage.buckets.getIamPolicy` |
| GCP-GCS-02 | - | `storage.buckets.list` (`iamConfiguration.uniformBucketLevelAccess`) |
| GCP-VPC-01 | - | `compute.firewalls.list` |
