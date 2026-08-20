// -------- Party popper burst + confetti on add-to-cart --------
function celebrateAddToCart() {
  const burst = document.createElement("div");
  burst.className = "popper-burst";
  burst.textContent = "🎉";
  document.body.appendChild(burst);
  setTimeout(() => burst.remove(), 900);

  if (window.confetti) {
    confetti({
      particleCount: 90,
      spread: 70,
      origin: { y: 0.65 },
      colors: ["#2563eb", "#f59e0b", "#16a34a", "#7c3aed"],
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // Add to cart via AJAX
  document.querySelectorAll(".add-cart-form").forEach((form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const formData = new FormData(form);
      const btn = form.querySelector("button");
      const originalText = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = "Adding...";

      try {
        const res = await fetch(form.action, { method: "POST", body: formData });
        const data = await res.json();
        if (data.ok) {
          celebrateAddToCart();
          const badge = document.getElementById("cart-count-badge");
          if (badge) badge.textContent = data.cart_count;
          btn.innerHTML = "Added ✓";
          setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 1200);
        } else {
          alert(data.message || "Could not add to cart.");
          btn.innerHTML = originalText;
          btn.disabled = false;
        }
      } catch (err) {
        alert("Something went wrong. Please try again.");
        btn.innerHTML = originalText;
        btn.disabled = false;
      }
    });
  });

  // Auto-dismiss flash toasts
  setTimeout(() => {
    document.querySelectorAll(".flash-toast").forEach((el) => {
      const alertInst = bootstrap.Alert.getOrCreateInstance(el);
      alertInst.close();
    });
  }, 4500);

  // Razorpay secure checkout
  document.querySelectorAll(".razorpay-pay-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const orderId = btn.dataset.orderId;
      const originalText = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = "Starting secure payment...";

      try {
        const res = await fetch(`/customer/orders/${orderId}/razorpay/create`, { method: "POST" });
        const data = await res.json();
        if (!data.ok) {
          alert(data.message || "Could not start payment.");
          btn.disabled = false;
          btn.innerHTML = originalText;
          return;
        }

        const options = {
          key: data.key_id,
          amount: data.amount,
          currency: data.currency,
          name: data.shop_name,
          description: `ShopHub Order #${orderId}`,
          order_id: data.razorpay_order_id,
          prefill: { name: data.customer_name, contact: data.customer_phone },
          theme: { color: "#2563eb" },
          handler: async function (response) {
            btn.innerHTML = "Verifying payment...";
            try {
              const verifyRes = await fetch(`/customer/orders/${orderId}/razorpay/verify`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(response),
              });
              const verifyData = await verifyRes.json();
              if (verifyData.ok) {
                celebrateAddToCart();
                setTimeout(() => window.location.reload(), 900);
              } else {
                alert(verifyData.message || "Payment verification failed.");
                btn.disabled = false;
                btn.innerHTML = originalText;
              }
            } catch (err) {
              alert("Could not verify payment. If money was deducted, contact the shop.");
              btn.disabled = false;
              btn.innerHTML = originalText;
            }
          },
          modal: {
            ondismiss: function () {
              btn.disabled = false;
              btn.innerHTML = originalText;
            },
          },
        };

        const rzp = new Razorpay(options);
        rzp.open();
      } catch (err) {
        alert("Something went wrong starting the payment.");
        btn.disabled = false;
        btn.innerHTML = originalText;
      }
    });
  });

  // Splash screen auto-redirect
  const splashRedirect = document.getElementById("splash-redirect-url");
  if (splashRedirect) {
    setTimeout(() => { window.location.href = splashRedirect.dataset.url; }, 2400);
  }
});
