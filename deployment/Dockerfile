# Use the AWS Lambda base image for Python 3.10
FROM public.ecr.aws/lambda/python:3.10

# Set home directory explicitly
ENV HOME=/root

# Switch to a temporary directory for setup
WORKDIR /tmp

# Switch back to the root directory
WORKDIR /

# Copy aws_setup script
RUN mkdir -p /opt
COPY aws_setup /opt/
RUN chmod +x /opt/aws_setup

# Install Node.js and Serverless framework
RUN curl --silent --location https://rpm.nodesource.com/setup_14.x | bash -
RUN yum install nodejs -y && npm install -g serverless

# Set up AWS credentials and region
VOLUME /aws/host:ro
VOLUME /code

ENV AWS_PROFILE=default
ENV AWS_DEFAULT_REGION=us-east-1

ENTRYPOINT ["/opt/aws_setup"]
CMD ["tail", "-f", "/dev/null"]