"""
Email confirmation sender — Gmail SMTP.

Setup (one-time):
  1. Google Account → Security → 2-Step Verification  (must be ON)
  2. Google Account → Security → App Passwords
  3. Generate password for "Mail" → copy the 16-char code
  4. Add to .env:
       GMAIL_USER=your.email@gmail.com
       GMAIL_APP_PASSWORD=abcdabcdabcdabcd
"""

from __future__ import annotations
import datetime
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from typing               import Tuple


def send_order_confirmation(order: dict) -> Tuple[bool, str]:
    """
    Send an HTML order-confirmation email via Gmail SMTP.
    Returns (success, human-readable message).
    """
    gmail_user = os.getenv("GMAIL_USER", "").strip()
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "").strip().replace(" ", "")

    if not gmail_user or not gmail_pass:
        return False, "Email not configured — add GMAIL_USER and GMAIL_APP_PASSWORD to .env"

    recipient = (order.get("shipping_info") or {}).get("email", "").strip()
    if not recipient:
        return False, "No recipient email address in order"

    oid = order.get("order_id", "—")

    msg = MIMEMultipart("alternative")
    msg["Subject"]    = f"✅ Order Confirmed — {oid} | ShopMind AI"
    msg["From"]       = f"ShopMind AI <{gmail_user}>"
    msg["To"]         = recipient
    msg["X-Priority"] = "1"

    msg.attach(MIMEText(_plain(order), "plain"))
    msg.attach(MIMEText(_html(order),  "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=12) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, recipient, msg.as_string())
        return True, f"Confirmation sent to {recipient}"
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail authentication failed — check GMAIL_APP_PASSWORD in .env"
    except smtplib.SMTPRecipientsRefused:
        return False, f"Invalid recipient address: {recipient}"
    except smtplib.SMTPException as exc:
        return False, f"SMTP error: {exc}"
    except OSError as exc:
        return False, f"Network error while sending email: {exc}"


def send_price_alert_email(watch: dict) -> Tuple[bool, str]:
    """
    Send a price-drop alert email when a watched product price drops.
    `watch` is a dict from PriceMonitor with new_price, old_price, drop_pct fields.
    """
    gmail_user = os.getenv("GMAIL_USER", "").strip()
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "").strip().replace(" ", "")
    if not gmail_user or not gmail_pass:
        return False, "Email not configured"

    recipient = watch.get("alert_email", "").strip()
    if not recipient:
        return False, "No alert email address set for this watch"

    name      = watch.get("name", "Product")[:60]
    new_price = watch.get("new_price", 0)
    old_price = watch.get("old_price", 0)
    drop_pct  = watch.get("drop_pct", 0)
    drop_amt  = watch.get("drop_amount", round(old_price - new_price))
    link      = watch.get("link", "")
    image     = watch.get("image", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"]    = f"🔔 Price Drop Alert — {name[:40]} dropped {drop_pct}% | ShopMind AI"
    msg["From"]       = f"ShopMind AI <{gmail_user}>"
    msg["To"]         = recipient
    msg["X-Priority"] = "1"

    plain = (
        f"Price Drop Alert!\n\n"
        f"Product: {name}\n"
        f"Old Price: ₹{int(old_price):,}\n"
        f"New Price: ₹{int(new_price):,}\n"
        f"You Save:  ₹{int(drop_amt):,} ({drop_pct}% off)\n"
        + (f"\nBuy now: {link}\n" if link else "")
        + f"\n— ShopMind AI"
    )

    img_html = (
        f'<img src="{image}" style="width:120px;height:auto;border-radius:8px;'
        f'object-fit:contain;" alt="product">'
        if image else ""
    )
    buy_btn = (
        f'<a href="{link}" style="display:inline-block;margin-top:18px;'
        f'background:linear-gradient(135deg,#7c6bf3,#b06ef3);color:#fff;'
        f'text-decoration:none;padding:12px 28px;border-radius:50px;'
        f'font-weight:700;font-size:15px;">🛒 Buy Now</a>'
        if link else ""
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Price Drop Alert</title></head>
<body style="margin:0;padding:0;background:#f3f4f6;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:32px 16px;">
      <table role="presentation" width="580" cellpadding="0" cellspacing="0"
        style="max-width:580px;width:100%;">
        <tr><td style="background:linear-gradient(135deg,#7c6bf3,#b06ef3);
          border-radius:16px 16px 0 0;padding:30px 40px;text-align:center;">
          <div style="font-size:32px;">🛍️</div>
          <h1 style="margin:6px 0 0;color:#fff;font-size:22px;font-weight:800;">ShopMind AI</h1>
        </td></tr>
        <tr><td style="background:#fff;padding:40px;text-align:center;">
          <div style="font-size:52px;margin-bottom:8px;">🔔</div>
          <h2 style="margin:0 0 6px;color:#111;font-size:24px;font-weight:800;">Price Drop!</h2>
          <p style="color:#6b7280;font-size:14px;margin:0 0 24px;">
            A product on your watch list just dropped in price.
          </p>
          {img_html}
          <div style="margin:20px auto;max-width:480px;background:#f5f3ff;
            border:1.5px solid #c4b5fd;border-radius:12px;padding:22px 28px;text-align:left;">
            <p style="margin:0 0 10px;font-size:14px;font-weight:700;color:#374151;">{name}</p>
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="font-size:13px;color:#6b7280;padding:4px 0;">Was</td>
                <td style="text-align:right;font-size:14px;color:#9ca3af;
                  text-decoration:line-through;">₹{int(old_price):,}</td>
              </tr>
              <tr>
                <td style="font-size:15px;font-weight:700;color:#4f46e5;padding:4px 0;">Now</td>
                <td style="text-align:right;font-size:22px;font-weight:800;color:#4f46e5;">
                  ₹{int(new_price):,}</td>
              </tr>
            </table>
            <div style="margin-top:14px;background:#dcfce7;border-left:3px solid #16a34a;
              border-radius:6px;padding:10px 14px;">
              <span style="color:#15803d;font-weight:700;font-size:14px;">
                💰 You save ₹{int(drop_amt):,} — {drop_pct}% off!
              </span>
            </div>
          </div>
          {buy_btn}
        </td></tr>
        <tr><td style="background:linear-gradient(135deg,#7c6bf3,#b06ef3);
          border-radius:0 0 16px 16px;padding:22px 40px;text-align:center;">
          <p style="margin:0;color:rgba(255,255,255,0.7);font-size:12px;">
            © 2025 ShopMind AI · You're receiving this because you set a price alert.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html,  "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=12) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, recipient, msg.as_string())
        return True, f"Price alert sent to {recipient}"
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail auth failed"
    except Exception as exc:
        return False, f"Email error: {exc}"


def send_cancellation_email(order: dict) -> Tuple[bool, str]:
    """
    Send an HTML order-cancellation email via Gmail SMTP.
    Returns (success, human-readable message).
    """
    gmail_user = os.getenv("GMAIL_USER", "").strip()
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "").strip().replace(" ", "")

    if not gmail_user or not gmail_pass:
        return False, "Email not configured — add GMAIL_USER and GMAIL_APP_PASSWORD to .env"

    recipient = (order.get("shipping_info") or {}).get("email", "").strip()
    if not recipient:
        return False, "No recipient email address in order"

    oid = order.get("order_id", "—")

    msg = MIMEMultipart("alternative")
    msg["Subject"]    = f"❌ Order Cancelled — {oid} | ShopMind AI"
    msg["From"]       = f"ShopMind AI <{gmail_user}>"
    msg["To"]         = recipient
    msg["X-Priority"] = "1"

    msg.attach(MIMEText(_plain_cancel(order), "plain"))
    msg.attach(MIMEText(_html_cancel(order),  "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=12) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, recipient, msg.as_string())
        return True, f"Cancellation email sent to {recipient}"
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail authentication failed — check GMAIL_APP_PASSWORD in .env"
    except smtplib.SMTPRecipientsRefused:
        return False, f"Invalid recipient address: {recipient}"
    except smtplib.SMTPException as exc:
        return False, f"SMTP error: {exc}"
    except OSError as exc:
        return False, f"Network error while sending email: {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# Plain-text fallback
# ─────────────────────────────────────────────────────────────────────────────

def _plain(order: dict) -> str:
    ship  = order.get("shipping_info") or {}
    items = order.get("items", [])
    today = datetime.date.today()
    est   = f"{(today + datetime.timedelta(days=3)).strftime('%d %b')} – {(today + datetime.timedelta(days=5)).strftime('%d %b %Y')}"

    lines = [
        f"Order Confirmed — {order.get('order_id','—')}",
        f"{'='*50}",
        f"",
        f"Hello {ship.get('name','')},",
        f"Your ShopMind AI order has been confirmed!",
        f"",
        f"ITEMS ORDERED",
        f"{'-'*40}",
    ]
    for it in items:
        lines.append(f"  {it['name'][:52]:52s}  x{it['qty']}  ₹{int(it['total']):>8,}")
    lines += [
        f"{'-'*40}",
        f"  {'Subtotal':52s}       ₹{order.get('subtotal',0):>8,.0f}",
        f"  {'GST (18%)':52s}       ₹{order.get('tax',0):>8,.2f}",
        f"  {'Shipping':52s}       {'FREE' if order.get('shipping',0)==0 else '₹'+str(int(order.get('shipping',0))):>8}",
        f"  {'TOTAL':52s}       ₹{order.get('total',0):>8,.2f}",
        f"",
        f"DELIVERY ADDRESS",
        f"  {ship.get('name','')}",
        f"  {ship.get('address','')}",
        f"  {ship.get('city','')} — {ship.get('pincode','')}",
        f"  {ship.get('phone','')}",
        f"",
        f"ESTIMATED DELIVERY:  {est}",
        f"PAYMENT ID:          {order.get('payment_id','')}",
        f"",
        f"Thank you for shopping with ShopMind AI!",
        f"Powered by Anthropic Claude & SerpAPI",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# HTML email
# ─────────────────────────────────────────────────────────────────────────────

def _html(order: dict) -> str:
    ship  = order.get("shipping_info") or {}
    items = order.get("items", [])
    oid   = order.get("order_id", "—")
    total = order.get("total", 0)
    pay_id = order.get("payment_id", "")

    today    = datetime.date.today()
    est_from = (today + datetime.timedelta(days=3)).strftime("%d %b")
    est_to   = (today + datetime.timedelta(days=5)).strftime("%d %b %Y")

    method_map = {
        "UPI":    "UPI Payment",
        "CARD":   "Credit / Debit Card",
        "NB":     "Net Banking",
        "WALLET": "Digital Wallet",
        "COD":    "Cash on Delivery",
        "DEMO":   "Demo Payment",
    }
    method = next((v for k, v in method_map.items() if pay_id.startswith(k)), "Online Payment")

    # Build item rows
    item_rows = ""
    for it in items:
        src_tag = (
            f'<br><span style="font-size:11px;color:#9ca3af;">🏪 {it["source"]}</span>'
            if it.get("source") else ""
        )
        name_cell = (
            f'<a href="{it["link"]}" style="color:#4f46e5;text-decoration:none;font-weight:600;">'
            f'{it["name"][:55]}</a>{src_tag}'
            if it.get("link")
            else f'<span style="font-weight:600;color:#111;">{it["name"][:55]}</span>{src_tag}'
        )
        item_rows += f"""
          <tr>
            <td style="padding:13px 16px;border-bottom:1px solid #f3f4f6;font-size:13.5px;
              color:#374151;line-height:1.5;">{name_cell}</td>
            <td style="padding:13px 16px;border-bottom:1px solid #f3f4f6;text-align:center;
              font-size:13px;color:#6b7280;">×{it['qty']}</td>
            <td style="padding:13px 16px;border-bottom:1px solid #f3f4f6;text-align:right;
              font-size:14px;font-weight:700;color:#111;">₹{int(it['total']):,}</td>
          </tr>"""

    shipping_str = "🎉 FREE" if order.get("shipping", 0) == 0 else f"₹{int(order.get('shipping', 0)):,}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Order Confirmed — {oid}</title>
</head>
<body style="margin:0;padding:0;background-color:#f3f4f6;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0"
          style="max-width:600px;width:100%;">

          <!-- ── HEADER ── -->
          <tr>
            <td style="background:linear-gradient(135deg,#7c6bf3 0%,#b06ef3 100%);
              border-radius:16px 16px 0 0;padding:36px 40px 28px;text-align:center;">
              <div style="font-size:36px;margin-bottom:10px;">🛍️</div>
              <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:800;
                letter-spacing:-0.3px;">ShopMind AI</h1>
              <p style="margin:6px 0 0;color:rgba(255,255,255,0.7);font-size:13px;">
                Powered by Anthropic Claude
              </p>
            </td>
          </tr>

          <!-- ── SUCCESS BANNER ── -->
          <tr>
            <td style="background:#ffffff;padding:40px 40px 28px;text-align:center;">
              <div style="font-size:56px;line-height:1;margin-bottom:16px;">🎉</div>
              <h2 style="margin:0 0 10px;color:#111827;font-size:26px;font-weight:800;">
                Order Confirmed!
              </h2>
              <p style="margin:0 0 24px;color:#4b5563;font-size:15px;">
                Hey <strong>{ship.get('name','')}</strong>, your order is placed and on its way!
              </p>
              <div style="display:inline-block;background:#f5f3ff;border:1.5px solid #c4b5fd;
                border-radius:10px;padding:12px 28px;">
                <span style="display:block;font-size:11px;color:#7c3aed;font-weight:700;
                  text-transform:uppercase;letter-spacing:1.2px;margin-bottom:4px;">
                  Order ID
                </span>
                <span style="font-family:'Courier New',monospace;font-size:20px;
                  font-weight:800;color:#4f46e5;">
                  {oid}
                </span>
              </div>
            </td>
          </tr>

          <!-- ── ITEMS TABLE ── -->
          <tr>
            <td style="background:#ffffff;padding:0 40px 28px;">
              <h3 style="margin:0 0 12px;font-size:15px;font-weight:700;color:#111;">
                🛒 Items Ordered
              </h3>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                style="border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;">
                <thead>
                  <tr style="background:linear-gradient(135deg,#7c6bf3,#b06ef3);">
                    <th style="padding:12px 16px;color:#fff;text-align:left;
                      font-size:12px;font-weight:700;text-transform:uppercase;
                      letter-spacing:0.5px;">Product</th>
                    <th style="padding:12px 16px;color:#fff;text-align:center;
                      font-size:12px;font-weight:700;text-transform:uppercase;">Qty</th>
                    <th style="padding:12px 16px;color:#fff;text-align:right;
                      font-size:12px;font-weight:700;text-transform:uppercase;">Amount</th>
                  </tr>
                </thead>
                <tbody>{item_rows}</tbody>
                <tfoot>
                  <tr style="background:#fafafa;">
                    <td colspan="2" style="padding:10px 16px;font-size:13px;color:#6b7280;">
                      Subtotal</td>
                    <td style="padding:10px 16px;text-align:right;font-size:13px;color:#374151;">
                      ₹{order.get('subtotal',0):,.0f}</td>
                  </tr>
                  <tr style="background:#fafafa;">
                    <td colspan="2" style="padding:7px 16px;font-size:13px;color:#6b7280;">
                      GST (18%)</td>
                    <td style="padding:7px 16px;text-align:right;font-size:13px;color:#374151;">
                      ₹{order.get('tax',0):,.2f}</td>
                  </tr>
                  <tr style="background:#fafafa;">
                    <td colspan="2" style="padding:7px 16px;font-size:13px;color:#6b7280;">
                      Shipping</td>
                    <td style="padding:7px 16px;text-align:right;font-size:13px;color:#374151;">
                      {shipping_str}</td>
                  </tr>
                  <tr style="background:#f5f3ff;border-top:2px solid #c4b5fd;">
                    <td colspan="2" style="padding:14px 16px;font-size:16px;
                      font-weight:700;color:#4f46e5;">Total Paid</td>
                    <td style="padding:14px 16px;text-align:right;font-size:20px;
                      font-weight:800;color:#4f46e5;">₹{total:,.2f}</td>
                  </tr>
                </tfoot>
              </table>
            </td>
          </tr>

          <!-- ── DELIVERY + PAYMENT ── -->
          <tr>
            <td style="background:#ffffff;padding:0 40px 36px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <!-- Delivery -->
                  <td width="50%" style="vertical-align:top;padding-right:8px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                      style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;">
                      <tr>
                        <td style="padding:18px;">
                          <p style="margin:0 0 10px;font-weight:700;font-size:14px;color:#111;">
                            🚚 Delivery Details
                          </p>
                          <p style="margin:0 0 5px;font-size:13px;font-weight:600;color:#374151;">
                            {ship.get('name','')}
                          </p>
                          <p style="margin:0 0 5px;font-size:12.5px;color:#6b7280;line-height:1.6;">
                            {ship.get('address','')}<br>
                            {ship.get('city','')} – {ship.get('pincode','')}
                          </p>
                          <p style="margin:0 0 10px;font-size:12.5px;color:#6b7280;">
                            📱 {ship.get('phone','')}
                          </p>
                          <div style="background:#dcfce7;border-left:3px solid #16a34a;
                            border-radius:6px;padding:9px 12px;">
                            <span style="font-size:11px;color:#15803d;font-weight:700;
                              text-transform:uppercase;letter-spacing:0.5px;">
                              Estimated Delivery
                            </span><br>
                            <span style="font-size:13px;font-weight:700;color:#15803d;">
                              📦 {est_from} – {est_to}
                            </span>
                          </div>
                        </td>
                      </tr>
                    </table>
                  </td>
                  <!-- Payment -->
                  <td width="50%" style="vertical-align:top;padding-left:8px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                      style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;">
                      <tr>
                        <td style="padding:18px;">
                          <p style="margin:0 0 10px;font-weight:700;font-size:14px;color:#111;">
                            💳 Payment Info
                          </p>
                          <p style="margin:0 0 6px;font-size:13px;color:#374151;">
                            Method: <strong>{method}</strong>
                          </p>
                          <p style="margin:0 0 6px;font-size:12px;color:#6b7280;">
                            Payment ID:
                          </p>
                          <code style="display:block;background:#ede9fe;color:#4f46e5;
                            font-size:11.5px;padding:6px 10px;border-radius:5px;
                            word-break:break-all;">{pay_id}</code>
                          <div style="margin-top:12px;background:#dbeafe;
                            border-left:3px solid #2563eb;border-radius:6px;padding:9px 12px;">
                            <span style="font-size:12px;color:#1d4ed8;font-weight:700;">
                              ✅ Payment Successful
                            </span>
                          </div>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- ── FOOTER ── -->
          <tr>
            <td style="background:linear-gradient(135deg,#7c6bf3,#b06ef3);
              border-radius:0 0 16px 16px;padding:28px 40px;text-align:center;">
              <p style="margin:0 0 6px;color:rgba(255,255,255,0.9);font-size:13.5px;
                font-weight:600;">
                Thank you for shopping with ShopMind AI! 🎊
              </p>
              <p style="margin:0;color:rgba(255,255,255,0.55);font-size:12px;">
                © 2025 ShopMind AI · Powered by Anthropic Claude &amp; SerpAPI
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Cancellation plain-text + HTML
# ─────────────────────────────────────────────────────────────────────────────

def _plain_cancel(order: dict) -> str:
    ship  = order.get("shipping_info") or {}
    items = order.get("items", [])
    lines = [
        f"Order Cancelled — {order.get('order_id','—')}",
        f"{'='*50}",
        f"",
        f"Hello {ship.get('name','')},",
        f"Your ShopMind AI order has been successfully cancelled.",
        f"",
        f"CANCELLED ITEMS",
        f"{'-'*40}",
    ]
    for it in items:
        lines.append(f"  {it['name'][:52]:52s}  x{it['qty']}  ₹{int(it['total']):>8,}")
    lines += [
        f"{'-'*40}",
        f"  {'Order Total':52s}       ₹{order.get('total',0):>8,.2f}",
        f"",
        f"If you paid online, your refund will be processed within 5–7 business days.",
        f"",
        f"We hope to see you again soon!",
        f"ShopMind AI · Powered by Anthropic Claude & SerpAPI",
    ]
    return "\n".join(lines)


def _html_cancel(order: dict) -> str:
    ship  = order.get("shipping_info") or {}
    items = order.get("items", [])
    oid   = order.get("order_id", "—")
    total = order.get("total", 0)
    pay_id = order.get("payment_id", "")

    method_map = {
        "UPI":    "UPI Payment",
        "CARD":   "Credit / Debit Card",
        "NB":     "Net Banking",
        "WALLET": "Digital Wallet",
        "COD":    "Cash on Delivery",
        "DEMO":   "Demo Payment",
    }
    method = next((v for k, v in method_map.items() if pay_id.startswith(k)), "Online Payment")
    refund_note = (
        "No charge was made." if pay_id.startswith("COD")
        else "Your refund will be processed within <strong>5–7 business days</strong>."
    )

    item_rows = ""
    for it in items:
        item_rows += f"""
          <tr>
            <td style="padding:12px 16px;border-bottom:1px solid #f3f4f6;font-size:13.5px;
              color:#374151;">{it['name'][:55]}</td>
            <td style="padding:12px 16px;border-bottom:1px solid #f3f4f6;text-align:center;
              font-size:13px;color:#6b7280;">×{it['qty']}</td>
            <td style="padding:12px 16px;border-bottom:1px solid #f3f4f6;text-align:right;
              font-size:14px;font-weight:700;color:#6b7280;
              text-decoration:line-through;">₹{int(it['total']):,}</td>
          </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Order Cancelled — {oid}</title>
</head>
<body style="margin:0;padding:0;background-color:#f3f4f6;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0"
          style="max-width:600px;width:100%;">

          <!-- HEADER -->
          <tr>
            <td style="background:linear-gradient(135deg,#7c6bf3 0%,#b06ef3 100%);
              border-radius:16px 16px 0 0;padding:36px 40px 28px;text-align:center;">
              <div style="font-size:36px;margin-bottom:10px;">🛍️</div>
              <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:800;">ShopMind AI</h1>
              <p style="margin:6px 0 0;color:rgba(255,255,255,0.7);font-size:13px;">
                Powered by Anthropic Claude
              </p>
            </td>
          </tr>

          <!-- CANCEL BANNER -->
          <tr>
            <td style="background:#ffffff;padding:40px 40px 28px;text-align:center;">
              <div style="font-size:56px;line-height:1;margin-bottom:16px;">😔</div>
              <h2 style="margin:0 0 10px;color:#111827;font-size:26px;font-weight:800;">
                Order Cancelled
              </h2>
              <p style="margin:0 0 24px;color:#4b5563;font-size:15px;">
                Hi <strong>{ship.get('name','')}</strong>, your order has been cancelled as requested.
              </p>
              <div style="display:inline-block;background:#fef2f2;border:1.5px solid #fca5a5;
                border-radius:10px;padding:12px 28px;">
                <span style="display:block;font-size:11px;color:#dc2626;font-weight:700;
                  text-transform:uppercase;letter-spacing:1.2px;margin-bottom:4px;">
                  Cancelled Order ID
                </span>
                <span style="font-family:'Courier New',monospace;font-size:20px;
                  font-weight:800;color:#b91c1c;">
                  {oid}
                </span>
              </div>
            </td>
          </tr>

          <!-- ITEMS TABLE -->
          <tr>
            <td style="background:#ffffff;padding:0 40px 28px;">
              <h3 style="margin:0 0 12px;font-size:15px;font-weight:700;color:#111;">
                🛒 Cancelled Items
              </h3>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                style="border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;">
                <thead>
                  <tr style="background:#6b7280;">
                    <th style="padding:12px 16px;color:#fff;text-align:left;font-size:12px;
                      font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Product</th>
                    <th style="padding:12px 16px;color:#fff;text-align:center;font-size:12px;
                      font-weight:700;text-transform:uppercase;">Qty</th>
                    <th style="padding:12px 16px;color:#fff;text-align:right;font-size:12px;
                      font-weight:700;text-transform:uppercase;">Amount</th>
                  </tr>
                </thead>
                <tbody>{item_rows}</tbody>
                <tfoot>
                  <tr style="background:#fef2f2;border-top:2px solid #fca5a5;">
                    <td colspan="2" style="padding:14px 16px;font-size:16px;font-weight:700;
                      color:#b91c1c;">Order Total (Cancelled)</td>
                    <td style="padding:14px 16px;text-align:right;font-size:20px;font-weight:800;
                      color:#b91c1c;text-decoration:line-through;">₹{total:,.2f}</td>
                  </tr>
                </tfoot>
              </table>
            </td>
          </tr>

          <!-- REFUND INFO -->
          <tr>
            <td style="background:#ffffff;padding:0 40px 36px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                style="background:#fffbeb;border:1px solid #fcd34d;border-radius:10px;">
                <tr>
                  <td style="padding:20px 24px;">
                    <p style="margin:0 0 8px;font-weight:700;font-size:14px;color:#92400e;">
                      💰 Refund Information
                    </p>
                    <p style="margin:0 0 6px;font-size:13px;color:#78350f;">
                      Payment method: <strong>{method}</strong>
                    </p>
                    <p style="margin:0;font-size:13px;color:#78350f;">{refund_note}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background:linear-gradient(135deg,#7c6bf3,#b06ef3);
              border-radius:0 0 16px 16px;padding:28px 40px;text-align:center;">
              <p style="margin:0 0 6px;color:rgba(255,255,255,0.9);font-size:13.5px;
                font-weight:600;">
                We hope to see you again soon! 💜
              </p>
              <p style="margin:0;color:rgba(255,255,255,0.55);font-size:12px;">
                © 2025 ShopMind AI · Powered by Anthropic Claude &amp; SerpAPI
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
