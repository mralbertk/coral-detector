# Deploy on Amazon Web Services 

## Summary
This is a serverless implementation of the solution on Amazon Web Services. 

- The application frontend runs in ECS Fargate
- All compute workloads are handled by Amazon Lambda
- Statistical coral data is stored in Amazon Aurora

## Architecture 
![](imgs/architecture-serverless.png)

## Requirement 
- To successfully deploy the application, you will need two detectron2 models:
  - `detectron2-reframe.pth` trained for reframing
  - `detectron2-classifier.pth` trained for coral detection
- The code to create these models is available in [notebooks](../../notebooks) 
- Unfortunately, we cannot make pre-trained models or labelled training sets available

## Use
- The streamlit web interface is available at the public endpoint of your Fargate cluster
- For general usage instructions, view the top-level [documentation](../../README.md)

## Deployment 
- There is no simple deployment available for this version - sorry!

### AWS Infrastructure Setup 
In a region of your choice, create:

#### Resources 
- 7 S3 buckets
- 4 ECR repositories 
- 3 Lambda functions using the code from [/workers](/workers)
- 1 Fargate Cluster implementing [frontend-definition.json](app/frontend-definition.json)
- 1 Aurora Cluster with a MYSQL database
- (Optional) 1 Route 53 hosted zone with an application load balancer

#### Parameters
```
cluster-credentials     # Your Aurora cluster credentials
db-cluster-arn          # The ARN of your Aurora cluster
db-name                 # The name of the Aurora DB you created
s3_images_raw           # The name of the S3 bucket you created for raw images
s3_images_treated       # The name of the S3 bucket you created for restored images
s3_images_reframed      # The name of the S3 bucket you created for reframed images
s3_images_segmented     # The name of the S3 bucket you created for segmented images
s3_images_masks         # The name of the S3 bucket you created for binary masks
s3_model_reframing      # The name of the S3 bucket you created for the reframing model
s3_model_segmentation   # The name of the S3 bucket you created for the segmentation model
```

### AWS Services Configuration

#### Aurora 
On your Aurora MYSQL database, execute the following script:

```sql
CREATE TABLE IF NOT EXISTS coral_coverage(
    island VARCHAR(30) NOT NULL,
    location INT NOT NULL,
    year INT NOT NULL,
    coverage DECIMAL(5,2) NOT NULL,
    last_update DATE NOT NULL,
    PRIMARY KEY (island, location, year)
);
```

#### Lambda 
Create the following triggers for your lambda functions:

- `restoration` is triggered by upload to `s3_images_raw`
- `reframing` is triggered by upload to `s3_images_treated`
- `segmentation` is triggered by upload to `s3_images_reframed`

#### Access Management
- At least one IAM role granting permissions to:
  - Read from and write to the S3 buckets 
  - Write to and Read from the Aurora cluster
- Assign this role to the Lambda functions and the Fargate cluster
- [Configure a github-actions-role for your AWS account](https://www.automat-it.com/post/using-github-actions-with-aws-iam-roles)

#### Deployment Parameters 
- Create the following action secrets in your repository: 

```
AWS_IAM_ROLE                # The ARN of the AWS IAM github actions role you configured
ECR_REGISTRY                # The ARN of the ECR repository holding your containers
ECR_FRONTEND_APP            # The name of the container for the streamlit frontend app
ECR_REFRAMING_LAMBDA        # The name of the container for the reframing worker
ECR_RESTORATION_LAMBDA      # The name of the container for the restoration worker           
ECR_SEGMENTATION_LAMBDA     # The name of the container for the segmentation worker
LAMBDA_IMAGE_REFRAMING      # The name of your lambda function for image reframing
LAMBDA_IMAGE_RESTORATION    # The name of your lambda function for image restoration
LAMBDA_IMAGE_SEGMENTATION   # The name of your lambda function for image segmentation
```

### Pushing Code 
If everything is configured correcly, you can push code as follows:
1. Manually by executing the corresponding github workflows 
2. Automatically each time code changes are pushed to the frontend or any worker

## Known Issues & Limitations 
- Refer to the top-level [documentation](../../ISSUES.md)