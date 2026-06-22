# Digital Twin Voice Agent

There are videos that accompany this demo.

- For the no-code setup walkthrough, watch: [https://youtu.be/-u9eKMotob4](https://youtu.be/-u9eKMotob4)
- For the Python version where we add tool calling (including Tavily web search) go here: [https://youtu.be/YBB2UWPh5Rs](https://youtu.be/YBB2UWPh5Rs)
- And for the version where we give the AI Voice Agent the power of email with [agentmail.to](http://agentmail.to) go here: [https://youtu.be/dMX_44VNqUg](https://youtu.be/dMX_44VNqUg)

## Prerequisites and Environment Setup

- Python 3.11+
- Cartesia account and CLI configured
- Anthropic API key
- Tavily API key
- [Agentmail.to](https://agentmail.to) API key and Inbox ID
- Cartesia voice clone ID from play.cartesia.ai
- LinkedIn profile PDF saved locally as `profile.pdf`

Copy `.env.example` to `.env`, then set:

```sh
ANTHROPIC_API_KEY=
TAVILY_API_KEY=
AGENTMAIL_API_KEY=
AGENTMAIL_INBOX_ID=
USER_EMAIL= # the email you want the voice agent to email you alerts at
VOICE_CLONE_ID= # watch the no code video to get this
```

## Running Steps

1. In one terminal:

```sh
uv sync
uv run python main.py
```

The app starts a Cartesia Line voice agent that answers from the prompt, reads `profile.pdf` when needed, and can use Tavily for web search/extract.

2. In a second terminal:
```sh
cartesia chat 8000
```
This will be a text only interaction with the voice agent - ideal for testing and development.  

You'll need to run `cartesia deploy` to push it to a Cartesia-hosted deployment environment.  You can also add a U.S. phone number to your voice agent via the playground at [play.cartesia.ai](https://play.cartesia.ai).

Watch the videos for full details, or just go to [docs.cartesia.ai](https://docs.cartesia.ai).
