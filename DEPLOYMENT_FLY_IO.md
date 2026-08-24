# Fly.io deployment

This project runs on Fly.io as one Machine using the existing Dockerfile. The bot uses Telegram long polling, so it does not need a public domain or webhook port.

SQLite needs persistent Fly Volume storage. Fly Volumes are local to a region and cannot be shared between Machines, so run exactly one Machine for this app.

## 1. Install and authenticate flyctl

Install flyctl using the official instructions at https://fly.io/docs/flyctl/install/.

Then sign in:

    fly auth login

## 2. Create the Fly app

Clone the repository locally and enter it:

    git clone https://github.com/Shevik11/personal-bot.git
    cd personal-bot

Create the app configuration without deploying immediately:

    fly launch --no-deploy

Choose a globally unique app name, for example personal-bot-yourname, and select a region near you. This command creates fly.toml. Do not add an HTTP service; this bot uses long polling.

Edit fly.toml and make sure it contains a mount for the database:

    [mounts]
      source = "data"
      destination = "/app/data"
      snapshot_retention = 14

The Dockerfile already sets SHOPPING_NOTES_DB to /app/data/shopping_notes.db.

## 3. Create the persistent volume

Use the same region selected for the app. Replace APP_NAME and REGION with your values:

    fly volumes create data --app APP_NAME --region REGION --size 1 --snapshot-retention 14

Fly takes daily volume snapshots by default. The command above keeps new snapshots for 14 days. Never destroy this volume unless you have a separate backup.

## 4. Configure secrets

Set the Telegram token as a Fly secret:

    fly secrets set TELEGRAM_BOT_TOKEN="replace-with-the-token-from-BotFather" --app APP_NAME

Optional non-secret settings can be placed in fly.toml:

    [env]
      BOT_TIMEZONE = "Europe/Kyiv"
      BIRTHDAY_ALERT_TIME = "09:00"
      BIRTHDAY_SUMMARY_TIME = "09:05"

Do not commit .env or put tokens in fly.toml. Fly secrets are injected as environment variables at runtime.

## 5. Deploy

Deploy from the repository directory:

    fly deploy --app APP_NAME

The bot runs migrations automatically before polling starts. Check the deployment:

    fly status --app APP_NAME
    fly logs --app APP_NAME

Then test /start, /shopping, /finance, /birthdays, /todo, and /events in Telegram.

Ensure only one Machine is running:

    fly scale count 1 --app APP_NAME

This is important because the database is SQLite and the birthday scheduler must not run in duplicate.

## 6. Update the bot

After pushing changes to Git:

    git pull --ff-only origin main
    fly deploy --app APP_NAME
    fly logs --app APP_NAME

The Fly Volume remains attached during normal deployments.

## 7. Backups and recovery

List the app volume:

    fly volumes list --app APP_NAME

Create an on-demand snapshot:

    fly volumes snapshots create VOLUME_ID

List available snapshots:

    fly volumes snapshots list VOLUME_ID

Fly snapshots are useful for recovery, but keep an additional copy for important data. A snapshot can be restored into a new volume with:

    fly volumes create data_restore --app APP_NAME --region REGION --snapshot-id SNAPSHOT_ID --size 1

Do not delete the original volume until the restored volume and database have been verified.

## Troubleshooting

View app status and logs:

    fly status --app APP_NAME
    fly logs --app APP_NAME
    fly machine list --app APP_NAME

Open a shell in the running Machine:

    fly ssh console --app APP_NAME

Inside the Machine, check storage:

    df -h
    ls -la /app/data

If startup fails, verify TELEGRAM_BOT_TOKEN, confirm that the volume is mounted at /app/data, and check that no other bot process is using the same Telegram token. Check BOT_TIMEZONE if birthday alerts run at an unexpected time.

Useful official references:

- Fly Launch: https://fly.io/docs/reference/fly-launch/
- App configuration and mounts: https://fly.io/docs/reference/configuration/
- Secrets: https://fly.io/docs/apps/secrets/
- Volumes: https://fly.io/docs/volumes/
- Volume snapshots: https://fly.io/docs/volumes/snapshots/
