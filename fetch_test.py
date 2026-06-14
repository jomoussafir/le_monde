import argparse
import os
import ssl
from http.cookiejar import MozillaCookieJar
from importlib import import_module
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, HTTPCookieProcessor, Request, build_opener

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def is_client_challenge_html(html):
    lower = html.lower()
    return "<title>client challenge</title>" in lower or "_fs-ch-" in lower


def _create_verified_ssl_context():
    """Create an HTTPS context, preferring certifi CA bundle when available."""
    try:
        certifi = import_module("certifi")
    except ModuleNotFoundError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def _is_cert_verification_error(exc):
    reason = getattr(exc, "reason", None)
    if isinstance(reason, ssl.SSLCertVerificationError):
        return True
    return "CERTIFICATE_VERIFY_FAILED" in str(exc)


def build_http_opener(cookie_file=None, ssl_context=None):
    handlers = []
    if ssl_context is not None:
        handlers.append(HTTPSHandler(context=ssl_context))
    if cookie_file:
        jar = MozillaCookieJar(str(cookie_file))
        if Path(cookie_file).exists():
            jar.load(ignore_discard=True, ignore_expires=True)
        handlers.append(HTTPCookieProcessor(jar))
    return build_opener(*handlers)


def fetch_url(url, cookie_file=None, timeout=30):
    insecure_ssl = os.getenv("LE_MONDE_INSECURE_SSL", "0") == "1"
    ssl_context = ssl._create_unverified_context() if insecure_ssl else _create_verified_ssl_context()
    opener = build_http_opener(cookie_file=cookie_file, ssl_context=ssl_context)
    req = Request(url, headers={
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    try:
        with opener.open(req, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except URLError as exc:
        if _is_cert_verification_error(exc) and not insecure_ssl:
            raise RuntimeError(
                "SSL certificate verification failed. Install a CA bundle (e.g. `pip install certifi`) "
                "or temporarily retry with LE_MONDE_INSECURE_SSL=1."
            ) from exc
        raise


def fetch_url_with_playwright(url, headless=False, interactive_challenge=False):
    try:
        sync_playwright = import_module("playwright.sync_api").sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright is required for browser fetch. Install with: pip install playwright && playwright install chromium"
        ) from exc

    user_data_dir = Path(__file__).with_name("user_data")
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=headless,
            channel="chrome",
            user_agent=DEFAULT_USER_AGENT,
        )
        try:
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                # Some pages keep long-lived connections; domcontentloaded is enough to read HTML.
                pass

            html = page.content()

            if is_client_challenge_html(html):
                if interactive_challenge and not headless:
                    print("Client challenge detected. Solve it in the opened browser, then press Enter.")
                    input()
                    page.reload(wait_until="domcontentloaded", timeout=90000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    html = page.content()

                if is_client_challenge_html(html):
                    raise RuntimeError(
                        "Client challenge page returned. Use interactive browser mode and solve the challenge manually."
                    )

            return html
        finally:
            context.close()


def fetch_url_auto(
    url,
    cookie_file=None,
    timeout=30,
    prefer_playwright=False,
    interactive_challenge=False,
):
    if prefer_playwright:
        return fetch_url_with_playwright(
            url,
            headless=not interactive_challenge,
            interactive_challenge=interactive_challenge,
        )

    html = fetch_url(url, cookie_file=cookie_file, timeout=timeout)
    if is_client_challenge_html(html):
        return fetch_url_with_playwright(
            url,
            headless=not interactive_challenge,
            interactive_challenge=interactive_challenge,
        )
    return html


def fetch_with_playwright_auth(url, output_file):
    try:
        sync_playwright = import_module("playwright.sync_api").sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright is not installed in this Python environment. Install it with: pip install playwright"
        ) from exc

    user_data_dir = Path(__file__).with_name("user_data")
    output_path = Path(output_file).expanduser().resolve()

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=False,
            user_agent=DEFAULT_USER_AGENT,
        )
        page = context.new_page()
        page.goto(url)
        input("Log in manually in the browser window, then press Enter here...")
        page.wait_for_load_state("networkidle")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(page.content(), encoding="utf-8")
        context.close()


def main():
    parser = argparse.ArgumentParser(description="Fetch a URL and save its HTML content.")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("output_file", help="Output HTML file path")
    parser.add_argument(
        "--cookie-file",
        default=None,
        help="Optional Netscape cookie file to authenticate requests",
    )
    parser.add_argument(
        "--use-playwright",
        action="store_true",
        help="Use interactive Playwright session instead of urllib",
    )
    args = parser.parse_args()

    output_path = Path(args.output_file).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.use_playwright:
        fetch_with_playwright_auth(args.url, str(output_path))
        print(f"Saved to {output_path}")
        return

    try:
        content = fetch_url(args.url, cookie_file=args.cookie_file)
    except (HTTPError, URLError, RuntimeError) as exc:
        raise RuntimeError(f"Failed to fetch {args.url}: {exc}") from exc

    output_path.write_text(content, encoding="utf-8")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
