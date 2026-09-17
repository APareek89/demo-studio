#!/usr/bin/env bash
# Provision the Demo Studio server on EC2. Idempotent: safe to re-run.
#
#   REGION      ap-south-1 (Mumbai) — same region as the existing S3 bucket, so media transfer is free and fast
#   INSTANCE    t3.micro (free tier, 1 GB RAM) + a 2 GB swap file, because ffmpeg transcodes need more than 1 GB
#   DISK        20 GB gp3 (free tier allows 30)
#   ADDRESS     Elastic IP, so the address survives a reboot. HTTPS name is <ip>.sslip.io
#   HTTPS       Caddy gets a Let's Encrypt certificate automatically. Required: the player uses the
#               microphone, and browsers only allow that on HTTPS.
set -euo pipefail

REGION="${REGION:-ap-south-1}"
NAME="${NAME:-demo-studio}"
TYPE="${TYPE:-t3.micro}"
AWS="${AWS:-.venv/bin/aws}"

say() { printf "\n\033[1m==> %s\033[0m\n" "$*"; }

say "Finding the newest Amazon Linux 2023 image"
AMI=$($AWS ec2 describe-images --region "$REGION" --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023*-x86_64" "Name=state,Values=available" \
  --query 'sort_by(Images,&CreationDate)[-1].ImageId' --output text)
echo "    $AMI"

say "Firewall: allow SSH from this laptop only, plus HTTP/HTTPS from anywhere"
MYIP=$(curl -s https://checkip.amazonaws.com | tr -d '\n')
SG=$($AWS ec2 describe-security-groups --region "$REGION" --group-names "$NAME-sg" \
      --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)
if [ -z "$SG" ] || [ "$SG" = "None" ]; then
  SG=$($AWS ec2 create-security-group --region "$REGION" --group-name "$NAME-sg" \
        --description "Demo Studio web server" --query 'GroupId' --output text)
  $AWS ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG" \
      --ip-permissions \
        "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=${MYIP}/32,Description=laptop-ssh}]" \
        "IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=0.0.0.0/0,Description=http-for-cert}]" \
        "IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=0.0.0.0/0,Description=https}]" >/dev/null
fi
echo "    $SG  (SSH locked to $MYIP)"

say "SSH key"
KEY_PATH="$HOME/.ssh/${NAME}.pem"
if [ ! -f "$KEY_PATH" ]; then
  $AWS ec2 create-key-pair --region "$REGION" --key-name "$NAME" \
      --query 'KeyMaterial' --output text > "$KEY_PATH"
  chmod 400 "$KEY_PATH"
fi
echo "    $KEY_PATH"

say "Launching $TYPE"
EXISTING=$($AWS ec2 describe-instances --region "$REGION" \
  --filters "Name=tag:Name,Values=$NAME" "Name=instance-state-name,Values=running,pending" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || true)
if [ -n "$EXISTING" ] && [ "$EXISTING" != "None" ]; then
  IID="$EXISTING"; echo "    reusing $IID"
else
  IID=$($AWS ec2 run-instances --region "$REGION" --image-id "$AMI" --instance-type "$TYPE" --count 1 \
      --key-name "$NAME" --security-group-ids "$SG" \
      --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=20,VolumeType=gp3,DeleteOnTermination=true}' \
      --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]" \
      --user-data file://docs/aws/ec2-userdata.sh \
      --query 'Instances[0].InstanceId' --output text)
  echo "    $IID"
fi

say "Waiting for it to boot"
$AWS ec2 wait instance-running --region "$REGION" --instance-ids "$IID"

say "Attaching a permanent address"
EIP=$($AWS ec2 describe-addresses --region "$REGION" --filters "Name=tag:Name,Values=$NAME" \
      --query 'Addresses[0].PublicIp' --output text 2>/dev/null || true)
if [ -z "$EIP" ] || [ "$EIP" = "None" ]; then
  ALLOC=$($AWS ec2 allocate-address --region "$REGION" --domain vpc \
          --tag-specification "ResourceType=elastic-ip,Tags=[{Key=Name,Value=$NAME}]" \
          --query 'AllocationId' --output text)
  $AWS ec2 associate-address --region "$REGION" --instance-id "$IID" --allocation-id "$ALLOC" >/dev/null
  EIP=$($AWS ec2 describe-addresses --region "$REGION" --allocation-ids "$ALLOC" \
        --query 'Addresses[0].PublicIp' --output text)
fi

say "Done"
echo "    instance : $IID"
echo "    address  : $EIP"
echo "    ssh      : ssh -i $KEY_PATH ec2-user@$EIP"
echo "    url      : https://${EIP//./-}.sslip.io"
