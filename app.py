import os
import stripe

from dotenv import load_dotenv
from flask import Flask, request, render_template, jsonify

load_dotenv()

# Retrieve API key and webhook secret from environment variables
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

app = Flask(__name__,
    static_url_path='',
    template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "views"),
    static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "public"))

# Book catalog as single source of truth for pricing + display
BOOKS = {
    '1': {
        'title': 'The Art of Doing Science and Engineering',
        'author': 'Richard Hamming',
        'amount': 2300,
        'description': 'The Art of Doing Science and Engineering is a reminder that a childlike capacity for learning and creativity are accessible to everyone.',
        'image': '/images/art-science-eng.jpg',
    },
    '2': {
        'title': 'The Making of Prince of Persia: Journals 1985-1993',
        'author': 'Jordan Mechner',
        'amount': 2500,
        'description': 'In The Making of Prince of Persia, on the 30th anniversary of the game’s release, Mechner looks back at the journals he kept from 1985 to 1993..',
        'image': '/images/prince-of-persia.jpg',
    },
    '3': {
        'title': 'Working in Public: The Making and Maintenance of Open Source',
        'author': 'Nadia Eghbal',
        'amount': 2800,
        'description': 'Nadia Eghbal takes an inside look at modern open source and offers a model through which to understand the challenges faced by online creators.',
        'image': '/images/working-in-public.jpg',
    },
}


# Home route
# Pass BOOKS so the template renders cards from data, not hardcoded HTML
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', books=BOOKS)


# Checkout route 
# Look up book, pass details + publishable key to the template
@app.route('/checkout', methods=['GET'])
def checkout():
    item = request.args.get('item')
    book = BOOKS.get(item)

    if not book:
        return render_template('checkout.html', error='No item selected')

    return render_template('checkout.html', title=book['title'], amount=book['amount'], item=item, 
        publishable_key=os.getenv('STRIPE_PUBLISHABLE_KEY'))


# Create PaymentIntent (API endpoint)
# Called by checkout.js to retrieve client_secret for the Payment Element
@app.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    data = request.get_json()

    # Validate item ID
    item = data.get('item') if data else None
    book = BOOKS.get(item)
    if not book:
        return jsonify(error='Invalid item'), 400

    try:
        intent = stripe.PaymentIntent.create(
            amount=book['amount'],
            currency='usd',
            automatic_payment_methods={'enabled': True}, 
            metadata={
                'item_id': item,
                'book_title': book['title'],
            },
            idempotency_key=data.get('idempotencyKey'), 
        )
        return jsonify(clientSecret=intent.client_secret, paymentIntentId=intent.id)

    except stripe.error.StripeError as e:
        return jsonify(error=str(e.user_message or e)), 400


# --- Webhook endpoint ---
# Stripe sends events here for reliable server-side confirmation
@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400

    # Trigger fulfillment (ship book, send email, update DB).
    # Persist event.id to handle webhook idempotency
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        print(f"[webhook] Payment succeeded: {payment_intent['id']} "
              f"for ${payment_intent['amount'] / 100:.2f}")

    return '', 200


# Success route
@app.route('/success', methods=['GET'])
def success():
    payment_intent_id = request.args.get('payment_intent')

    if not payment_intent_id:
        return render_template('success.html', error='No payment information found')

    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
    except stripe.error.StripeError:
        return render_template('success.html', error='Unable to retrieve payment details')

    # Only show confirmation if the payment actually succeeded
    if intent.status != 'succeeded':
        return render_template('success.html', error='Payment has not been completed')

    return render_template('success.html', payment_intent_id=intent.id, amount=intent.amount, status=intent.status)


if __name__ == '__main__':
    app.run(port=5000, host='0.0.0.0', debug=True)
