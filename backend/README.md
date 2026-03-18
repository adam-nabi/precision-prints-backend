# Precision Prints Backend

This is the smallest backend restart for your 3D printing business system.

It does three useful things right now:

- serves real order data over HTTP
- lets you fetch one order or all orders
- lets you update an order status
- lets a lead scout create dashboard orders from Reddit/Discord-style leads

## Files

- `app/main.py`: FastAPI routes
- `app/models.py`: shared order and status models
- `app/store.py`: JSON file loading and saving
- `data/orders.json`: starter data
- `requirements.txt`: Python packages

## Run Locally

From the `backend` folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/orders`
- `http://127.0.0.1:8000/docs`

## What This Gives You

This is the first backend step toward:

- SwiftUI dashboard loading live orders
- quote and status management
- later Stripe payment links
- later shipping label prep
- later Reddit/Discord/lead ingestion
- later STL download and analysis

## Manual Payment Links

This backend now supports a simple manual payment-link workflow.

New route:

```text
PATCH /orders/{order_id}/payment-link
```

Request body:

```json
{
  "paymentLinkURL": "https://..."
}
```

What it does:

- saves a manual payment link onto the order
- moves the order to `Pending Payment`
- lets the iPhone app open that link

## Pricing Settings

The backend now stores pricing settings so the app can control quote inputs.

Routes:

```text
GET /pricing-settings
PUT /pricing-settings
```

Example response:

```json
{
  "baseOrderFee": 5.0,
  "materialMarkupMultiplier": 1.35,
  "hourlyPrintRate": 4.0,
  "complexitySurcharge": 3.0,
  "shippingMarkupFlat": 1.5
}
```

## Lead Intake

This backend now supports a simple lead-ingestion route so your future Reddit or Discord scout can create dashboard orders automatically.

Route:

```text
POST /lead-intake
```

Example request:

```json
{
  "source": "Reddit",
  "customerName": "u/print-help-92",
  "messageText": "Can someone print this for me in black? https://www.printables.com/model/12345-part",
  "sourceURL": "https://reddit.com/...",
  "modelURL": "https://files.printables.com/media/.../part.stl",
  "quantity": 2
}
```

What it does:

- creates a new dashboard order
- sets the order to `New Lead` when a model link is included
- sets the order to `Manual Review` when the lead is missing a model link
- saves the source message into notes
- stores the model link so the iPhone app can open it

## Reddit and Discord Scout

This backend now has a simple scout route for Reddit and Discord messages.

Route:

```text
POST /scout/messages
```

What it does:

- checks whether a message looks like a 3D print request
- looks for Thingiverse, Printables, MakerWorld, Cults3D, Thangs, STL, 3MF, or ZIP links
- creates a dashboard order when it finds a likely lead
- keeps unsupported materials in `Manual Review`

Important shop rule:

- the system is now limited to `PLA` and `PETG`
- requests for ASA, ABS, resin, TPU, nylon, or carbon-fiber materials are flagged for review

Example request:

```json
{
  "source": "Discord",
  "customerName": "Casey T.",
  "messageText": "Can someone 3D print this for me in PETG? https://www.printables.com/model/12345-part",
  "sourceURL": "https://discord.com/channels/..."
}
```

## Real Reddit Imports

This backend can now scan real Reddit posts and turn matching ones into dashboard orders.

Route:

```text
POST /integrations/reddit/scan
```

Required environment variables:

- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USERNAME`
- `REDDIT_PASSWORD`
- `REDDIT_SUBREDDITS`

Optional:

- `REDDIT_USER_AGENT`
- `REDDIT_LIMIT`

What it does:

- fetches recent posts from the configured subreddits
- checks whether the post looks like a 3D print request
- imports matching posts as orders
- skips posts it already imported before

## Important Next Step

Once this API is running, the next smallest app change is:

1. make the iPhone app fetch `/orders`
2. keep the same `Order` JSON shape
3. later add `PATCH /orders/{id}/status` from the app

## Host It Online

The simplest hosted path is Render.

Current official docs I checked:

- [Deploy a FastAPI App](https://render.com/docs/deploy-fastapi)
- [Blueprint YAML Reference](https://render.com/docs/blueprint-spec)
- [Monorepo Support](https://render.com/docs/monorepo-support)

This repo now includes a root [render.yaml](/Users/Adam/Desktop/PrecisionPrintsApp/render.yaml) that points Render at the `backend` folder.

### Simple Render Steps

1. Push this repo to GitHub.
2. Create a Render account.
3. In Render, create a new Blueprint or Web Service from the GitHub repo.
4. Let Render read `render.yaml`.
5. Wait for the deploy to finish.
6. Open your public backend URL and test `/health` and `/orders`.

### Important Note About Data

Render web services use an ephemeral filesystem by default.

That means:

- your backend code will deploy fine
- but JSON file changes can be lost on redeploy or restart

For a serious production version, the next step after hosting is moving order storage to a real database like Postgres.

## Compliance Note

Automated monitoring and outreach on Reddit, Discord, and similar platforms must follow each platform's API, automation, spam, and rate-limit rules. The safe path is to start with approved ingestion methods, manual review, and draft generation before any automated outbound messaging.
