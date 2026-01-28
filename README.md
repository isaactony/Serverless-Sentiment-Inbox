# Serverless Sentiment Inbox

A serverless AWS solution that automatically processes email files (.eml) uploaded to S3, analyzes sentiment using Amazon Comprehend, calculates urgency based on keywords, and organizes emails into sorted folders.

## How It Works

1. Upload a `.eml` file to the `raw/` prefix in the S3 bucket
2. S3 triggers a Lambda function on object creation
3. Lambda parses the email (subject, from, body)
4. Amazon Comprehend analyzes sentiment (POSITIVE, NEGATIVE, NEUTRAL, MIXED)
5. Urgency is calculated based on keyword presence (high/medium/low)
6. Email is copied to `sorted/{sentiment}/{urgency}/`
7. Analysis JSON file is created with metadata and results

## Architecture

- **S3 Bucket**: Stores emails with versioning and encryption
- **Lambda Function**: Python 3.11 runtime, processes emails automatically
- **Amazon Comprehend**: Sentiment analysis service
- **IAM Roles**: Least-privilege permissions for security

## Prerequisites

- AWS account with appropriate permissions
- Terraform >= 1.0
- AWS CLI configured with credentials

## Deployment

1. Navigate to the infrastructure directory:
```bash
cd infra
```

2. Initialize Terraform:
```bash
terraform init
```

3. Create a `terraform.tfvars` file with your configuration:
```hcl
aws_region           = "us-east-1"
bucket_name          = "your-unique-bucket-name"
lambda_function_name = "email-sentiment-processor"
```

4. Review the plan:
```bash
terraform plan
```

5. Deploy the infrastructure:
```bash
terraform apply
```

## Testing

1. Upload a test `.eml` file to the S3 bucket's `raw/` prefix:
```bash
aws s3 cp test-email.eml s3://your-bucket-name/raw/test-email.eml
```

2. Check CloudWatch Logs for the Lambda function to see processing details

3. Verify the email was copied to the sorted location:
```bash
aws s3 ls s3://your-bucket-name/sorted/ --recursive
```

4. Download and review the analysis JSON:
```bash
aws s3 cp s3://your-bucket-name/sorted/{sentiment}/{urgency}/test-email.analysis.json .
```

## Urgency Keywords

- **High**: urgent, asap, immediate, critical, emergency, as soon as possible
- **Medium**: important, priority, soon, deadline, needs attention
- **Low**: Default when no keywords are found


## Cleanup

To remove all resources:
```bash
cd infra
terraform destroy
```
