# "Why Replit" + a one-hour build to back it up

## The three beats (about 60 seconds total)

1. **I know this stage.** At Cohesity I watched security features become deal unblockers.
   Replit is moving upmarket (Enterprise: SSO/SAML, SCIM, RBAC, audit logs, single-tenant
   hosting), and at that stage a bank's security review decides the deal.
2. **The problem is new.** Non-engineers and AI agents ship real apps. Isolation,
   secrets, and identity for code nobody hand-wrote is a harder version of what I've been doing.
3. **It's where I want to grow:** deep AI security and infrastructure at enterprise scale.

*(Double-check the latest public numbers the week before, and quote only what you've verified.)*

## The build: TLS certificate expiry checker (about an hour, with Replit Agent)

**Prompt to Replit Agent**
> Build a small web app: I paste a list of domains (one per line). For each, it connects
> on 443, and shows the certificate issuer, the full chain, the SANs, and days until expiry.
> Anything under 30 days is red. Add an optional "alert" button that posts results to a
> webhook URL stored as a secret. Then deploy it.

**What to watch, and note down as you go**

| Area | Question | What you saw |
|---|---|---|
| Secrets | Where does Agent put the webhook URL? Does it ever hardcode it or log it? | |
| Input handling | Does it validate domains? Could I make it connect to `localhost`, `169.254.169.254`, or an internal IP (SSRF)? | |
| Deployment | What does the deployment run on? What's exposed by default (ports, debug endpoints)? | |
| Auth | Is the deployed app public by default? How do you restrict it? | |
| Security scan | Run their security scan. What did it catch? What did it miss (for example, SSRF)? | |
| Dependencies | What did Agent pull in? Pinned versions? | |

The SSRF check is the one to try: a cert checker that connects to arbitrary hosts is a
textbook SSRF vector, which makes it a very natural security-buyer observation.

**Your interview line (fill it in after building)**
> "I built a cert checker on it last weekend. Agent handled ______ well. The thing I'd want
> as an enterprise security buyer is ______."
