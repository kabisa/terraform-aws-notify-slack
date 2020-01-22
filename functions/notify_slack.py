from __future__ import print_function
import os, boto3, json, base64
import urllib.request, urllib.parse
import logging

# Decrypt encrypted URL with KMS
def decrypt(encrypted_url):
    region = os.environ['AWS_REGION']
    try:
        kms = boto3.client('kms', region_name=region)
        plaintext = kms.decrypt(CiphertextBlob=base64.b64decode(encrypted_url))['Plaintext']
        return plaintext.decode()
    except Exception:
        logging.exception("Failed to decrypt URL with KMS")

# Send a message to a slack channel
def notify_slack(subject, message, region):
    slack_url = os.environ['SLACK_WEBHOOK_URL']
    if not slack_url.startswith("http"):
        slack_url = decrypt(slack_url)

    slack_channels = json.loads(os.environ['SLACK_CHANNELS'])
    slack_username = os.environ['SLACK_USERNAME']
    slack_emoji = os.environ['SLACK_EMOJI']

    for slack_channel in slack_channels:
        payload = {
        "channel": slack_channel,
        "username": slack_username,
        "icon_emoji": slack_emoji,
        "attachments": []
        }
        if type(message) is str:
            try:
                message = json.loads(message);
            except json.JSONDecodeError as err:
                logging.exception(f'JSON decode error: {err}')



        payload = format_message(payload, subject, message, region);

        data = urllib.parse.urlencode({"payload": json.dumps(payload)}).encode("utf-8")
        req = urllib.request.Request(slack_url)
        urllib.request.urlopen(req, data)


def lambda_handler(event, context):
    subject = event['Records'][0]['Sns']['Subject']
    message = event['Records'][0]['Sns']['Message']
    region = event['Records'][0]['Sns']['TopicArn'].split(":")[3]
    notify_slack(subject, message, region)

    return message


def format_message(payload, subject, message, region):
    if "AlarmName" in message:
        #cloudwatch notification
        return cloudwatch_notification(payload, message, region);
    else:
        return json_to_table_notification(payload, subject, message);


def cloudwatch_notification(payload, message, region):
    states = {'OK': 'good', 'INSUFFICIENT_DATA': 'warning', 'ALARM': 'danger'}

    attachments = {
            "color": states[message['NewStateValue']],
            "fallback": "Alarm {} triggered".format(message['AlarmName']),
            "footer": "AWS SNS Notification",
            "footer_icon": "https://www.kabisa.nl/favicon-f61d5679.png",
            "fields": [
                { "title": "Alarm Name", "value": message['AlarmName'], "short": True },
                { "title": "Alarm Description", "value": message['AlarmDescription'], "short": False},
                { "title": "Alarm reason", "value": message['NewStateReason'], "short": False},
                { "title": "Old State", "value": message['OldStateValue'], "short": True },
                { "title": "Current State", "value": message['NewStateValue'], "short": True },
                {
                    "title": "Link to Alarm",
                    "value": "https://console.aws.amazon.com/cloudwatch/home?region=" + region + "#alarm:alarmFilter=ANY;name=" + urllib.parse.quote_plus(message['AlarmName']),
                    "short": False
                }
            ]
        }

    payload['text'] = attachments["fallback"];
    payload['attachments'].append(attachments);

    return payload;

def json_to_table_notification(payload, subject, message):

    fields = [];

    for key, value in message.items():
        if isinstance(value, str) and len(value) > 30:
            fields.append({"title":key, "value": value, "short": False});
        else:
            fields.append({"title":key, "value": value, "short": True});

    attachments = {
            "fallback": "A new message",
            "fields": fields,
            "footer": "AWS SNS Notification",
            "footer_icon": "https://www.kabisa.nl/favicon-f61d5679.png"
        }

    payload['text'] = subject;
    payload['attachments'].append(attachments);

    return payload;


#notify_slack({"AlarmName":"Example","AlarmDescription":"Example alarm description.","AWSAccountId":"000000000000","NewStateValue":"ALARM","NewStateReason":"Threshold Crossed","StateChangeTime":"2017-01-12T16:30:42.236+0000","Region":"EU - Ireland","OldStateValue":"OK"}, "eu-west-1")
