# Schema Terraform Configuration

## Requirements
1. Download Terraform

    The configuration files are compatible with version v0.14.6
    ```
    $ terraform version
    Terraform v0.14.6
    + provider registry.terraform.io/hashicorp/aws v3.31.0
    ```
2. The route53 hosted zones should be pre-created and their name servers should be configured by the owner team of the parent domain. The steps for setting up subdomains for MorPhiC are enumerated [here](https://docs.google.com/document/d/1_L-c_PLWq-3DBGu_fjpN27RIo_WCbBJUKRvofzomv70/edit#heading=h.7gaksfkvzyjd).

Environment| Domain                                        | Parent Domain           |Owner
--- |-----------------------------------------------|-------------------------| --- 
prod| schema.morphic.bio                            | morphic.bio             | Domain management is performed on the `dev` AWS MorPhiC account through the Route53 service
dev| dev.schema.morphic.bio | morphic.bio | 


## To do
1. Add tags to AWS resources

## Create or update the schema instance
1. Go to directory containing Terraform configuration files for MorPhiC
   ```
   cd terraform/morphic
   ```
1. Initialize working directory
    ```
    source init.sh integration # or dev, staging, prod
    ```
1. (If update) Update the config or variable files (e.g. `.tf` files or `.tfvars`)

1. Apply the configuration
    ```
    terraform apply -var-file=integration.tfvars # or dev, staging, prod
    ```
1. Confirm the resources to be created or updated.

## Destroy

Run and confirm the resources to be deleted.
```
terraform destroy -var-file=integration.tfvars # or dev, staging, prod
```