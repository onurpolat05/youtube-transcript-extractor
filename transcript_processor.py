import os
from openai import OpenAI
import json
import time
import logging
from functools import wraps
import backoff
import re
from prompt_templates import get_template
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API anahtarını doğrudan .env'den oku ve OpenAI client'a ver
client = OpenAI(
    api_key=os.getenv('OPENAI_API_KEY', None)  # None varsayılan değer olarak
)

# Constants for rate limiting
RATE_LIMIT_DELAY = 10  # seconds between requests
MAX_RETRIES = 3

def rate_limit_decorator(min_delay=RATE_LIMIT_DELAY):
    """Decorator to implement rate limiting between API calls"""
    last_call = {}
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            last_time = last_call.get(func.__name__, 0)
            sleep_time = min_delay - (current_time - last_time)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            result = func(*args, **kwargs)
            last_call[func.__name__] = time.time()
            return result
        return wrapper
    return decorator

def validate_response(input_text, response):
    """Validate the OpenAI API response for proper text formatting."""
    if not response.get('formatted_text'):
        raise ValueError("Response missing formatted text")
    
    if response['formatted_text'] == input_text:
        raise ValueError("Formatted text unchanged from input")
        
    # Additional validation - ensure required fields exist
    required_fields = ['summary', 'tags', 'key_points']
    missing_fields = [field for field in required_fields if not response.get(field)]
    if missing_fields:
        raise ValueError(f"Response missing required fields: {', '.join(missing_fields)}")
    
    return True

def clean_and_transform_response(response_text):
    """Clean and transform OpenAI response text into proper JSON format."""
    try:
        # First try direct JSON parsing
        return json.loads(response_text)
    except json.JSONDecodeError:
        # Fallback parsing for malformed JSON
        try:
            # Clean up common JSON formatting issues
            cleaned_text = response_text.strip()
            # Remove any markdown formatting
            cleaned_text = re.sub(r'```json\s*|\s*```', '', cleaned_text)
            # Ensure proper quote usage
            cleaned_text = cleaned_text.replace("'", '"')
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            # If still failing, extract content using regex
            extracted = {
                'formatted_text': extract_field(response_text, 'formatted_text'),
                'summary': extract_field(response_text, 'summary'),
                'tags': extract_field(response_text, 'tags', is_list=True),
                'key_points': extract_field(response_text, 'key_points', is_list=True)
            }
            return extracted

def extract_field(text, field_name, is_list=False):
    """Extract field values from text using regex patterns."""
    if is_list:
        pattern = r'["\']?' + re.escape(field_name) + r'["\']?\s*:\s*\[(.*?)\]'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            items = re.findall(r'["\']([^"\']+)["\']', match.group(1))
            return items
        return []
    else:
        pattern = r'["\']?' + re.escape(field_name) + r'["\']?\s*:\s*["\']([^"\']+)["\']'
        match = re.search(pattern, text)
        return match.group(1) if match else ""

@rate_limit_decorator()
@backoff.on_exception(
    backoff.expo,
    (Exception,),
    max_tries=MAX_RETRIES,
    giveup=lambda e: isinstance(e, KeyError)
)
def process_transcript(transcript_text, style="default"):
    """Process transcript with OpenAI for formatting, summarization and tagging."""
    try:
        if not transcript_text or not isinstance(transcript_text, str):
            raise ValueError("Invalid transcript text provided")

        template = get_template(style)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": template["system_prompt"]
                },
                {"role": "user", "content": transcript_text}
            ],
            response_format=template["response_format"]
        )
        
        response_text = response.choices[0].message.content
        processed_response = clean_and_transform_response(response_text)
        
        # Validate the response
        validate_response(transcript_text, processed_response)
        
        return processed_response
    except Exception as e:
        logger.error(f"Failed to process transcript: {e}")
        raise Exception(f"Failed to process transcript: {str(e)}")

def batch_process_transcripts(transcripts, style="default"):
    """Process multiple transcripts with OpenAI with improved error handling and rate limiting."""
    if not transcripts or not isinstance(transcripts, list):
        raise ValueError("Invalid transcripts input: must be a non-empty list")

    if not client.api_key:
        raise ValueError("OpenAI API anahtarı bulunamadı!")

    results = []
    for transcript in transcripts:
        try:
            # Input validation
            if not isinstance(transcript, dict):
                raise ValueError(f"Invalid transcript format for video {transcript.get('video_id', 'unknown')}")
            
            if 'transcript' not in transcript or 'video_id' not in transcript:
                raise KeyError(f"Missing required fields for video {transcript.get('video_id', 'unknown')}")

            # Process transcript with rate limiting and retries
            processed = process_transcript(transcript['transcript'], style)
            
            results.append({
                'video_id': transcript['video_id'],
                'title': transcript.get('title', 'Unknown Title'),
                'formatted_text': processed.get('formatted_text', ''),
                'summary': processed.get('summary', ''),
                'tags': processed.get('tags', []),
                'key_points': processed.get('key_points', []),
                'full_transcript': transcript['transcript'],  # Original unformatted text
                'style': style,
                'research_implications': processed.get('research_implications', []),
                'code_snippets': processed.get('code_snippets', []),
                'technical_concepts': processed.get('technical_concepts', []),
                'market_insights': processed.get('market_insights', []),
                'strategic_implications': processed.get('strategic_implications', []),
                'success': True
            })
            
        except (ValueError, KeyError) as e:
            logger.error(f"Validation error for video {transcript.get('video_id', 'unknown')}: {e}")
            results.append({
                'video_id': transcript.get('video_id', 'unknown'),
                'error': str(e),
                'success': False,
                'error_type': 'validation_error'
            })
        except Exception as e:
            logger.error(f"Processing error for video {transcript.get('video_id', 'unknown')}: {e}")
            results.append({
                'video_id': transcript.get('video_id', 'unknown'),
                'error': str(e),
                'success': False,
                'error_type': 'processing_error'
            })

    if not any(result.get('success', False) for result in results):
        logger.error("All transcript processing attempts failed")
        raise Exception("Failed to process any transcripts successfully")

    return results
