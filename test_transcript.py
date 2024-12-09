import logging
from youtube_transcript_api import YouTubeTranscriptApi
from transcript_processor import clean_metadata_from_text
from openai import OpenAI
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def process_with_openai(transcript, video_id):
    """Process transcript with OpenAI."""
    # Join transcript text
    full_text = " ".join([entry['text'] for entry in transcript])
    
    # Prepare the prompt
    prompt = f"""Process this YouTube video transcript and provide:
1. A concise summary
2. Relevant tags
3. Key points
4. The formatted transcript

Video ID: {video_id}

Transcript:
{full_text}"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-16k",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise

def test_transcript_processing(video_id: str):
    """Test the transcript processing pipeline step by step."""
    
    # Step 1: Fetch transcript
    logger.info("="*80)
    logger.info("STEP 1: Fetching transcript")
    logger.info("="*80)
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        logger.info(f"Successfully fetched transcript with {len(transcript)} segments")
        logger.debug("First few segments:")
        for segment in transcript[:3]:
            logger.debug(json.dumps(segment, indent=2))
    except Exception as e:
        logger.error(f"Failed to fetch transcript: {e}")
        return

    # Step 2: Process with OpenAI
    logger.info("\n" + "="*80)
    logger.info("STEP 2: Processing with OpenAI")
    logger.info("="*80)
    try:
        raw_response = process_with_openai(transcript, video_id)
        logger.info("Successfully got OpenAI response")
        logger.debug("Raw response:")
        logger.debug("-"*40)
        logger.debug(raw_response)
        logger.debug("-"*40)
    except Exception as e:
        logger.error(f"Failed to process with OpenAI: {e}")
        return

    # Step 3: Clean metadata
    logger.info("\n" + "="*80)
    logger.info("STEP 3: Cleaning metadata")
    logger.info("="*80)
    try:
        cleaned_response = clean_metadata_from_text(raw_response)
        logger.info("Successfully cleaned metadata")
        logger.debug("Cleaned response:")
        logger.debug("-"*40)
        logger.debug(cleaned_response)
        logger.debug("-"*40)
    except Exception as e:
        logger.error(f"Failed to clean metadata: {e}")
        return

    logger.info("\n" + "="*80)
    logger.info("PROCESSING COMPLETE")
    logger.info("="*80)

if __name__ == "__main__":
    # Test with specific video ID
    VIDEO_ID = "rW2r5uStgG0"
    test_transcript_processing(VIDEO_ID)
