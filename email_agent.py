import asyncio
import os
from typing import Annotated, AsyncGenerator, Optional

from agentmail import AsyncAgentMail
from line.events import CallStarted, CallEnded, AgentSendText, UserTextSent, AgentTextSent
from line.llm_agent import LlmAgent, LlmConfig, ToolEnv, loopback_tool, end_call
from loguru import logger

from prompt import PROMPT, INTRODUCTION
from tools import read_resume, TavilyTools


"""
AgentMail integration for the Digital Twin voice agent.

- DigitalTwinAgent: Wrapper that intercepts call lifecycle events
- _build_transcript: Helper to format conversation history
- send_transcript: LLM-callable tool for emailing transcript to caller

"""


def _build_transcript(history, name: Optional[str] = None) -> str:
    """Walk agent history and build readable transcript."""
    transcript_entries = []
    user_name = name if name else "Caller"
    for event in history:
        if isinstance(event, UserTextSent):
            transcript_entries.append(f"{user_name}: {event.content}")
        elif isinstance(event, AgentTextSent):
            transcript_entries.append(f"Agent: {event.content}")
    return "\n\n".join(transcript_entries) if transcript_entries else "No transcript available."


class DigitalTwinAgent:
    """Wrapper that intercepts call lifecycle events for email notifications.
    
    On CallStarted: emails owner an alert (non-blocking)
    During call: send_transcript tool available to LLM
    On CallEnded: emails owner the full transcript
    """
    
    def __init__(self, call_request):
        # --- Validate env vars at runtime ---
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        agentmail_api_key = os.getenv("AGENTMAIL_API_KEY")
        inbox_id = os.getenv("AGENTMAIL_INBOX_ID")
        owner_email = os.getenv("USER_EMAIL")

        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        if not tavily_api_key:
            raise ValueError("TAVILY_API_KEY is not set")
        if not agentmail_api_key:
            raise ValueError("AGENTMAIL_API_KEY is not set")
        if not inbox_id:
            raise ValueError("AGENTMAIL_INBOX_ID is not set")
        if not owner_email:
            raise ValueError("USER_EMAIL is not set")

        # --- Store config ---
        self._inbox_id = inbox_id
        self._owner_email = owner_email
        self._agentmail_client = AsyncAgentMail(api_key=agentmail_api_key)
        self._call_request = call_request

        # --- Wire tools ---
        tavily = TavilyTools(api_key=tavily_api_key)

        # --- Create conversation agent ---
        self.llmAgent = LlmAgent(
            model="anthropic/claude-sonnet-4-6",
            api_key=anthropic_api_key,
            tools=[
                end_call,
                read_resume,
                tavily.web_search,
                tavily.web_extract,
                self.send_transcript_to_caller,
            ],
            config=LlmConfig(
                system_prompt=PROMPT,
                introduction=INTRODUCTION,
            ),
        )

    async def process(self, env, event):
        """The process method receives events (user speech, call start, etc.) and yields responses.

        get_agent accepts an agent is either:
        - A class with a process method; OR
        - A function with the same signature (env, event) -> AsyncIterable[OutputEvent]
        
        See: https://docs.cartesia.ai/line/sdk/agents#what-is-an-agent
        """
        # Alert owner on connect (non-blocking)
        if isinstance(event, CallStarted):
            asyncio.create_task(self._alert_owner_on_connect(env))

        # Email owner transcript after call ends (AFTER delegation — history must be final)
        if isinstance(event, CallEnded):
            await self._email_owner_transcript()

        # Delegate ALL events to conversation agent
        async for output in self.llmAgent.process(env, event):
            yield output

        

    async def _alert_owner_on_connect(self, env):
        """Send owner a connect alert when a caller connects.
        
        Called via asyncio.create_task() so it runs in the background.
        If the email fails, we log and continue — never block the call.

        Not called by the LLM, but by our call event-handling code here in the DigitalTwinAgent class.
        """
        try:
            logger.info(f"Sending connect alert to owner: {self._owner_email}")
            await self._agentmail_client.inboxes.messages.send(
                self._inbox_id,
                to=self._owner_email,
                subject="Attn: Digital Twin: New call connected",
                text=f"A caller just connected to your digital twin id: {env.agent_env.agent_id}, from "
                f"phone number: {self._call_request.from_}"
            )
        except Exception as e:
            logger.error(f"Failed to send connect alert: {e}")

    async def _email_owner_transcript(self):
        """Send owner the full transcript after the call ends.
        
        Called AFTER delegating CallEnded to llmAgent.process() so the
        history is complete. Reads from llmAgent.history which contains
        all UserTextSent and AgentTextSent events from the conversation.

        Not called by the LLM, but by our call event-handling code here in the DigitalTwinAgent class.
        """
        try:
            logger.info(f"Sending transcript to owner: {self._owner_email}")
            transcript = _build_transcript(self.llmAgent.history)
            await self._agentmail_client.inboxes.messages.send(
                self._inbox_id,
                to=self._owner_email,
                subject="Attn: Digital Twin: Call transcript",
                text=f"The call just ended.  Here is the transcript of the conversation: \n\n{transcript}",
            )
        except Exception as e:
            logger.error(f"Failed to send transcript to owner: {e}")

    @loopback_tool
    async def send_transcript_to_caller(
        self,
        ctx: ToolEnv,
        email: Annotated[str, "Email address to send transcript to"],
        name: Annotated[str, "Name of the caller if available. Leave blank if not available."],
    ) -> AsyncGenerator[AgentSendText, None]:
        """LLM-callable tool: email transcript to the caller.
        
        The LLM calls this when the caller asks for a transcript.
        Yields AgentSendText so the response is spoken aloud to the caller.
        On failure, we tell the caller honestly — don't claim success.
        """
        try:
            transcript = _build_transcript(self.llmAgent.history, name)
            greeting = f"Hi {name}" if name else "Hi"
            await self._agentmail_client.inboxes.messages.send(
                self._inbox_id,
                to=email,
                subject="As requested, your conversation with Zubin's Digital Twin",
                text=f"{greeting}, here is the transcript of the conversation: \n\n{transcript}",
            )
            yield AgentSendText(text="Done, I've sent the transcript to your email. Thanks for your call! Bye.")
        except Exception as e:
            logger.error(f"Failed to send transcript to caller: {e}")
            yield AgentSendText(text="Sorry, I wasn't able to send that email. Please try again.")