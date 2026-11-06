# Meta Instagram integration — official API

This project uses Instagram API with Instagram Login for professional accounts.
It never asks for Instagram passwords.

## Required setup

1. Create a Meta App at https://developers.facebook.com/apps
2. Enable Instagram API with Instagram Login and connect an eligible Business or Creator account.
3. Configure publicly reachable HTTPS webhook URL:
   https://YOUR-HOST/webhooks/instagram
4. Subscribe to the appropriate Instagram messaging and comment event fields.
5. Request permissions for the chosen flow. Common permissions include:
   instagram_business_basic
   instagram_business_manage_messages
   instagram_business_manage_comments
6. Complete any necessary review for your account type and access scope.
7. Provision valid tokens and configure environment variables on the server:
   META_APP_SECRET, META_VERIFY_TOKEN, META_ACCESS_TOKEN, META_IG_USER_ID
8. Recreate the running services using docker compose up -d --force-recreate.

Do not paste tokens into GitHub issues, committed source files or AI chat.

## Webhook verification

GET /webhooks/instagram checks hub.mode, hub.verify_token and returns hub.challenge.
POST /webhooks/instagram accepts only a valid X-Hub-Signature-256 HMAC over raw body.
Inbound DM/comment events are stored durably, de-duplicated and drafted by the worker.

## Outbound safety

Human review is required. Direct messages are further gated by a conservative
24-hour incoming-message age check. Public comment replies have a conservative
seven-day gate in this MVP. Meta policies and exceptions change; independently
verify the correct current permissions, endpoints and messaging windows before Live.

This release does not support unsolicited outbound marketing, image attachments,
OAuth self-service onboarding, automatic replies or token-refresh automation.

## Official references

- https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api
- https://developers.facebook.com/docs/instagram-platform/
