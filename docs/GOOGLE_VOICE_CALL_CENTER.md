# Mehrad Kavir Voice AI + Google Gemini — Setup Guide v0.3

**Status:** implemented integration paths with offline smoke tests; **NOT a validated live Iranian business telephone service**. Real operation requires the company's telephone/SIP operator, an accessible phone number, provider approvals, compatible live models, and a public HTTPS + WSS endpoint.

## Architecture

Inbound PSTN number → Twilio Programmable Voice webhook → signed callback → one-use stream ticket → bidirectional WebSocket Media Streams (G.711 mu-law 8 kHz) → PCM resampling to 16 kHz → Gemini Live (audio response PCM 24 kHz) → resampling back to 8 kHz → phone caller.

At the end of the call, text from Live transcriptions remains in memory unless the caller explicitly consents to contact-data retention. After consent: Gemini structured field extraction → encrypted candidate → owner review → CRM lead in qualifying stage.

No raw audio files are stored by this application. No outgoing marketing calls are implemented.

## 1. Connect Google AI Studio

1. Update the local project: run git pull origin main, followed by START-WINDOWS.bat in the local project folder.
2. Sign in to the dashboard, open Security & Connections, scroll to Google AI / Gemini.
3. Enter your Google AI Studio API key and select text, Live and TTS model identifiers. Sample values in the UI are gemini-3.8-flash, gemini-3.8-live and gemini-3.8-flash-tts. Actual model availability must be verified for your account.
4. Save the encrypted key; click the Google API model test button.
5. Optionally select Google Gemini as your default text provider for drafts, content scenarios and feedback proposals. OpenAI remains an alternative.
6. Open the Voice AI page and generate a Persian speech preview in the chosen voice. The button generates a WAV sample, not a telephone call.

The Google model-list metadata check does not guarantee Gemini Live or TTS access. Each must be tested independently.

## 2. Pilot inbound calls through Twilio

1. Acquire an actual Twilio Programmable Voice number supporting Media Streams.
2. Configure a public valid HTTPS domain (for example, https://voice.example.com). Provide WSS support on TCP 443. Do NOT publish port 8787 directly.
3. In the dashboard Security & Connections → Telephone, configure Twilio Account SID, Twilio Auth Token and your public HTTPS base URL.
4. Test Twilio account authentication. Then enable inbound reception only for controlled tests.
5. In the Twilio number's Voice webhook settings, set an HTTP POST URL:
   https://voice.example.com/voice/twilio/incoming
6. The signed response will provide the WSS Media Streams URL:
   wss://voice.example.com/voice/twilio/media
7. Call your test number. Check that Gemini introduces itself as an AI assistant in Iranian Persian and asks only necessary project questions.
8. Inspect the call in the Voice AI panel. If and only if the caller consented to retention, the system can produce an encrypted draft lead proposal. An owner must review before inserting the lead into CRM.

### Nginx reverse proxy guidance

For requests under /voice/twilio/media, proxy to the local backend with HTTP/1.1, the Upgrade and Connection: upgrade headers, and a read timeout longer than the maximum call duration. For incoming call webhooks, forward the POST body unchanged. Use a real TLS certificate, strict host matching and request throttling. Protect dashboard paths separately with VPN/IP rules. The backend validates Twilio signatures against the configured public URL, not against an untrusted forwarded host header.

This is a pilot implementation: exact bidirectional latency, barge-in, voice/transcript quality, region-specific provider signature behavior and call reconnection must be validated live.

## 3. What about an Iranian fixed/mobile number?

Twilio is a demonstrable provider adapter; its services do NOT guarantee an Iranian domestic inbound number. For the company's existing number, check with the operator whether calls can be delivered through a SIP trunk or a PBX (Asterisk/FreePBX). Current Asterisk versions support ARI ExternalMedia WebSocket streaming. This project does **not yet include an Asterisk/SIP media driver**.

You need from the company/provider: SIP trunk details, PBX version, incoming DID/extension, concurrent channel limit, codec, network permissions, TLS, legal recording/processing requirements and a real human-transfer destination. Once that is known, an Asterisk adapter can reuse the same Gemini Live dialogue engine and consent-reviewed CRM.

## 4. Security, privacy and limitations

- AI discloses its identity at the start of a call and tells the caller voice will be processed for the requested service.
- Caller may request human follow-up, but v0.3 does not claim instant transfer to a live employee.
- No price quotes, structural calculations or delivery guarantees without verified documents and an authorized human.
- Phone and transcript are stored encrypted only after both a deterministic consent gate and the structured extraction confirm affirmative contact consent.
- Users cannot make the bot disclose secrets, other customers' data or internal instructions. User speech is always untrusted data.
- Signed Twilio HTTP and WSS requests plus one-time stream ticket are required.
- No audio recordings; maximum call duration 360 seconds, two parallel calls per app process, bounded audio messages and transcript length.
- No auto-creation of a lead without human approval.
- Review legal obligations for AI notification, voice processing, retention and international data transfer before production.
- Model access, speech quality and actual phone access are unverified until connected to your accounts.

## References

Google Gemini API / Interactions:
https://ai.google.dev/gemini-api/docs/interactions-overview

Gemini Live:
https://ai.google.dev/gemini-api/docs/live-api/get-started-sdk

Gemini TTS:
https://ai.google.dev/gemini-api/docs/speech-generation

Twilio Media Streams:
https://www.twilio.com/docs/voice/media-streams

Twilio request signatures:
https://www.twilio.com/docs/usage/security

Asterisk ARI WebSocket:
https://docs.asterisk.org/Configuration/Channel-Drivers/WebSocket/
