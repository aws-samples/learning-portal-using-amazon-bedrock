from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_dynamodb as dynamodb, RemovalPolicy,
    aws_elasticloadbalancingv2 as elb_v2,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins, Duration,
)
from aws_cdk.aws_cloudfront import OriginProtocolPolicy, CachedMethods, GeoRestriction, CachePolicy

from constructs import Construct


class CdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, config: list, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create a VPC
        vpc = ec2.Vpc(
            self, "LearningDemoVPC",
            max_azs=2,
        )

        # Create ECS cluster
        cluster = ecs.Cluster(self, "LearningDemoCluster", vpc=vpc)

        # Add an AutoScalingGroup to the existing cluster
        cluster.add_capacity("LearningAsG",
                             max_capacity=5,
                             min_capacity=1,
                             desired_capacity=1,
                             instance_type=ec2.InstanceType("t3.small"),
                             )

        # Build Dockerfile from local folder and push to ECR
        image = ecs.ContainerImage.from_asset('webgui')

        task_definition = ecs.FargateTaskDefinition(
            self, 'LearningDemoTaskDefinition',
            cpu=1024, memory_limit_mib=4096)

        task_definition.add_to_execution_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            resources=["*"],
            actions=[
                "ecr:BatchCheckLayerAvailability",
                "ecr:BatchGetImage",
                "ecr:GetAuthorizationToken",
                "ecr:GetDownloadUrlForLayer",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
            ]
        ))
        task_definition.add_to_task_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            resources=["*"],
            actions=[
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "s3:*",
                "secretsmanager:GetSecretValue",
                "bedrock:*",
            ]
        ))

        container = task_definition.add_container(
            "LearningDemoContainer",
            image=image,
            environment={
                "s3_bucket_name": config["s3_bucket_name"],
                "ai21_api_key": config["ai21_api_key"],
            })
        container.add_port_mappings(ecs.PortMapping(container_port=8501, protocol=ecs.Protocol.TCP))

        fargate_service = ecs.FargateService(
            self, "LearningDemoFargateService", cluster=cluster, task_definition=task_definition)

        lb = elb_v2.ApplicationLoadBalancer(self, "LearningDemoLoadBalancer", vpc=vpc, internet_facing=True)
        listener = lb.add_listener("LearningDemoListener", port=80)

        listener.add_action(
            "DefaultAction",
            action=elb_v2.ListenerAction.fixed_response(
                500,
                content_type="text/plain",
                message_body="Denied Service"
            )
        )

        listener.add_targets(
            "LearningDemoListenerTarget",
            conditions=[elb_v2.ListenerCondition.http_header("X-Custom-Header", ["LearningDemo+9988"])],
            protocol=elb_v2.ApplicationProtocol.HTTP,
            priority=5,
            targets=[fargate_service.load_balancer_target(container_name="LearningDemoContainer", container_port=8501)])
        """fargate_service.attach_to_application_target_group(target_group)"""

        # Setup task auto-scaling
        scaling = fargate_service.auto_scale_task_count(
            max_capacity=5
        )

        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=50,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
        )

        cloudfront.Distribution(
            self, "LearningDemoDist",
            comment="Learning Demo CloudFront Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.LoadBalancerV2Origin(
                    lb,
                    custom_headers={"X-Custom-Header": "LearningDemo+9988"},
                    http_port=80,
                    protocol_policy=OriginProtocolPolicy.HTTP_ONLY,
                ),
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=CachePolicy.CACHING_OPTIMIZED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
            ),
            geo_restriction=GeoRestriction.allowlist("US")
        )

        # DynamoDB
        assignments_table_name = 'assignments'
        assignments_table = dynamodb.Table(
            self, 'questions_table',
            table_name=assignments_table_name,
            partition_key=dynamodb.Attribute(
                name='teacher_id',
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name='assignment_id',
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            stream=dynamodb.StreamViewType.NEW_IMAGE,
            removal_policy=RemovalPolicy.DESTROY
        )

        answers_table_name = 'answers'
        answers_table = dynamodb.Table(
            self, 'answers_table',
            table_name=answers_table_name,
            partition_key=dynamodb.Attribute(
                name='student_id',
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name='assignment_question_id',
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            stream=dynamodb.StreamViewType.NEW_IMAGE,
            removal_policy=RemovalPolicy.DESTROY
        )

        answers_table.add_global_secondary_index(
            index_name="assignment_question_id-index",
            partition_key=dynamodb.Attribute(
                name='assignment_question_id',
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        ecs_task_role = task_definition.task_role
        answers_table.grant_full_access(ecs_task_role)
        assignments_table.grant_full_access(ecs_task_role)
