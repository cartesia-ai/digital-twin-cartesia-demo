import os

from line.voice_agent_app import VoiceAgentApp, CallRequest, PreCallResult

from email_agent import DigitalTwinAgent

VOICE_CLONE_ID = os.getenv("VOICE_CLONE_ID") 
if not VOICE_CLONE_ID:
    raise ValueError("VOICE_CLONE_ID is not set")


async def pre_call_handler(call_request: CallRequest):
    """Set TTS config before call connects."""
    return PreCallResult(
        config={
            "tts": {
                "voice_id": VOICE_CLONE_ID,
                "model": "sonic-3.5",
                "language": "en",
            }
        }
    )


async def get_agent(env, call_request):
    return DigitalTwinAgent(call_request)


app = VoiceAgentApp(get_agent=get_agent, pre_call_handler=pre_call_handler)

if __name__ == "__main__":
    app.run()