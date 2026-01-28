import json
import boto3
import email
from email import policy
from email.parser import BytesParser
from datetime import datetime
from urllib.parse import unquote

s3_client = boto3.client('s3')
comprehend_client = boto3.client('comprehend')

# Urgency keywords with weights
URGENCY_KEYWORDS = {
    'high': ['urgent', 'asap', 'immediate', 'critical', 'emergency', 'as soon as possible'],
    'medium': ['important', 'priority', 'soon', 'deadline', 'needs attention'],
    'low': []  # Default if no keywords found
}

def calculate_urgency(subject, body):
    """
    Calculate urgency level based on keyword presence in subject and body.
    Returns: 'high', 'medium', or 'low'
    """
    text = f"{subject} {body}".lower()
    
    # Check for high urgency keywords first
    for keyword in URGENCY_KEYWORDS['high']:
        if keyword in text:
            return 'high'
    
    # Check for medium urgency keywords
    for keyword in URGENCY_KEYWORDS['medium']:
        if keyword in text:
            return 'medium'
    
    # Default to low if no keywords found
    return 'low'

def parse_eml_file(eml_content):
    """
    Parse .eml file content and extract subject, from, and body.
    Returns: dict with 'subject', 'from', 'body'
    """
    msg = BytesParser(policy=policy.default).parsebytes(eml_content)
    
    subject = msg.get('Subject', '')
    from_addr = msg.get('From', '')
    
    # Extract body text
    body = ''
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == 'text/plain':
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode('utf-8', errors='ignore')
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode('utf-8', errors='ignore')
    
    return {
        'subject': subject,
        'from': from_addr,
        'body': body
    }

def detect_sentiment(text):
    """
    Call Amazon Comprehend DetectSentiment API.
    Returns: dict with sentiment and scores
    """
    if not text or len(text.strip()) == 0:
        return {
            'Sentiment': 'NEUTRAL',
            'SentimentScore': {
                'Positive': 0.25,
                'Negative': 0.25,
                'Neutral': 0.25,
                'Mixed': 0.25
            }
        }
    
    # Comprehend has a 5000 byte limit per request
    # Truncate if necessary
    text_bytes = text.encode('utf-8')
    if len(text_bytes) > 5000:
        text = text_bytes[:5000].decode('utf-8', errors='ignore')
    
    response = comprehend_client.detect_sentiment(
        Text=text,
        LanguageCode='en'
    )
    
    return response

def lambda_handler(event, context):
    """
    Main Lambda handler for S3 object creation events.
    """
    try:
        # Extract S3 event details
        record = event['Records'][0]
        bucket_name = record['s3']['bucket']['name']
        object_key = unquote(record['s3']['object']['key'])
        
        # Only process .eml files
        if not object_key.endswith('.eml'):
            print(f"Skipping non-.eml file: {object_key}")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Skipped non-.eml file'})
            }
        
        print(f"Processing file: {object_key}")
        
        # Download .eml file from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        eml_content = response['Body'].read()
        
        # Parse email
        email_data = parse_eml_file(eml_content)
        
        # Combine subject and body for sentiment analysis
        analysis_text = f"{email_data['subject']} {email_data['body']}".strip()
        
        # Detect sentiment using Comprehend
        sentiment_result = detect_sentiment(analysis_text)
        sentiment = sentiment_result['Sentiment']
        sentiment_scores = sentiment_result['SentimentScore']
        
        # Calculate urgency
        urgency = calculate_urgency(email_data['subject'], email_data['body'])
        
        # Determine route: sorted/{sentiment}/{urgency}/
        route = f"{sentiment.lower()}/{urgency}"
        
        # Extract filename without extension
        filename = object_key.split('/')[-1].replace('.eml', '')
        
        # Copy object to sorted/{route}/
        new_key = f"sorted/{route}/{object_key.split('/')[-1]}"
        copy_source = {
            'Bucket': bucket_name,
            'Key': object_key
        }
        
        s3_client.copy_object(
            CopySource=copy_source,
            Bucket=bucket_name,
            Key=new_key
        )
        print(f"Copied file to: {new_key}")
        
        # Create analysis JSON
        analysis_data = {
            'filename': object_key.split('/')[-1],
            'original_key': object_key,
            'sorted_key': new_key,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'email_metadata': {
                'subject': email_data['subject'],
                'from': email_data['from']
            },
            'sentiment': {
                'sentiment': sentiment,
                'scores': sentiment_scores
            },
            'urgency': urgency,
            'route': route
        }
        
        # Write analysis JSON to S3
        analysis_key = f"sorted/{route}/{filename}.analysis.json"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=analysis_key,
            Body=json.dumps(analysis_data, indent=2),
            ContentType='application/json'
        )
        print(f"Created analysis file: {analysis_key}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Email processed successfully',
                'original_key': object_key,
                'sorted_key': new_key,
                'analysis_key': analysis_key,
                'sentiment': sentiment,
                'urgency': urgency
            })
        }
        
    except Exception as e:
        print(f"Error processing email: {str(e)}")
        raise e
