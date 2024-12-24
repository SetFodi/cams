# security.py
from flask_talisman import Talisman

def apply_security(app):
    # Enable HTTPS and apply CSP (can be customized later)
    talisman = Talisman(app, force_https=True)

    # CSP: Customize or add more security rules here as needed
    csp = {
        'default-src': ["'self'"],  # Only allow resources from the same domain
        'script-src': ["'self'", "'unsafe-inline'", "https://cdnjs.cloudflare.com"],  # Allow inline scripts and external CDN scripts
        'style-src': ["'self'", "'unsafe-inline'", "https://cdnjs.cloudflare.com"],  # Allow inline styles and external CDN styles
        'font-src': ["'self'", "https://cdnjs.cloudflare.com"],  # Allow fonts from the CDN
        'img-src': ["'self'", "data:"],  # Allow images from the same domain and data URIs
        'connect-src': ["'self'"],  # Allow XMLHttpRequests (AJAX) to same origin
        'frame-ancestors': ["'none'"],  # Prevent this app from being embedded in iframes (clickjacking protection)
    }

    # Apply the Content Security Policy
    talisman.content_security_policy = csp

    # Additional headers for enhanced security
    app.config['X_FRAME_OPTIONS'] = 'SAMEORIGIN'  # Prevent your site from being embedded in an iframe (clickjacking protection)
    app.config['X_XSS_PROTECTION'] = '1; mode=block'  # Enable cross-site scripting (XSS) filter
    app.config['X_CONTENT_TYPE_OPTIONS'] = 'nosniff'  # Prevent MIME type sniffing
    app.config['STRICT_TRANSPORT_SECURITY'] = 'max-age=31536000; includeSubDomains; preload'  # HSTS: Force HTTPS connections
    app.config['REFERRER_POLICY'] = 'no-referrer-when-downgrade'  # Control how referrer information is sent with requests

    # Limit HTTP methods to GET, POST, and HEAD only
    app.config['ALLOWED_METHODS'] = ['GET', 'POST', 'HEAD']

    # HTTP Headers for improved security
    app.config['CONTENT_SECURITY_POLICY'] = "default-src 'self';"
    app.config['X_CONTENT_TYPE_OPTIONS'] = 'nosniff'
    app.config['X_XSS_PROTECTION'] = '1; mode=block'
    app.config['STRICT_TRANSPORT_SECURITY'] = 'max-age=31536000; includeSubDomains'

    return talisman
