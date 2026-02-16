/**
 * Checkout with Stripe Payment Element and Address Element integration
 *
 */

document.addEventListener('DOMContentLoaded', async () => {
  // Read server-provided config from the form's data attributes
  const form = document.getElementById('payment-form');
  const publishableKey = form.dataset.publishableKey;
  const item = form.dataset.item;
  const returnUrl = form.dataset.returnUrl;

  const submitButton = document.getElementById('submit-button');
  const messageDiv = document.getElementById('payment-message');

  // Initialize Stripe
  const stripe = Stripe(publishableKey);

  //Create PaymentIntent
  const response = await fetch('/create-payment-intent', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      item: item,
      idempotencyKey: item + '_' + Date.now(),
    }),
  });
  const { clientSecret, paymentIntentId, error: backendError } = await response.json();

  if (backendError) {
    showMessage(backendError);
    return;
  }

  // Show the Payment Intent ID in the UI
  const piIdDiv = document.getElementById('payment-intent-id');
  if (piIdDiv) {
    piIdDiv.textContent = paymentIntentId;
    piIdDiv.closest('.d-none')?.classList.remove('d-none');
  }

  // Create Elements instance
  const appearance = { theme: 'stripe' };
  const elements = stripe.elements({ clientSecret, appearance });

  // Mount Link Element, collects email and handles Link
  const linkAuthElement = elements.create('linkAuthentication');
  linkAuthElement.mount('#link-auth-element');

  let emailValue = '';
  linkAuthElement.on('change', (event) => {
    emailValue = event.value.email;
  });

  // Mount Address Element
  const addressElement = elements.create('address', { mode: 'shipping' });
  addressElement.mount('#address-element');

  // Mount Payment Element
  const paymentElement = elements.create('payment', {
    business: { name: 'Stripe Press' },
    fields: { billingDetails: { email: 'never' } }, // Email handled by Link Auth Element above, so hide it here
  });
  paymentElement.mount('#payment-element');

  // Handle form submission
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    setLoading(true);

    // confirmPayment sends payment + address details to Stripe
    const { error } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: returnUrl,
        payment_method_data: {
          billing_details: { email: emailValue }, // Email from Link Auth Element is passed into billing_details
        },
      },
    });

    // error handling
    // error.message is Stripe's customer-safe error string
    if (error.type === 'card_error' || error.type === 'validation_error') {
      showMessage(error.message);
    } else {
      showMessage('An unexpected error occurred. Please try again.');
    }

    setLoading(false);
  });

  // Show an error or info message to the customer
  function showMessage(text) {
    messageDiv.textContent = text;
    messageDiv.classList.remove('d-none');
  }

  // Toggle button disabled state and text to prevent double-submits
  function setLoading(isLoading) {
    submitButton.disabled = isLoading;
    submitButton.textContent = isLoading ? 'Processing...' : submitButton.dataset.originalText;
  }

  // Store the original button text so we can restore it after errors
  submitButton.dataset.originalText = submitButton.textContent;
});
