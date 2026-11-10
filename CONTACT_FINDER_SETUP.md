# Free contact lookup

The project does not require SerpApi or another paid contact-search API.

For each business, the results table provides two manual search links:

- **Find email** opens a Google web search for the business and its location with email/contact terms.
- **Find Instagram** opens a Google search restricted to Instagram profile results.

After verifying that a result belongs to the correct business, click **Edit contacts**, enter the email or Instagram profile URL, and save it. The backend persists these values in PostgreSQL and the Google Sheets exporter includes them in the Contacts column.

Phone numbers are imported automatically when they are present in the Maps scraper output.

## Why contact lookup is manual

The chosen Maps scraper can extract emails from business websites when that feature is enabled, but this workflow deliberately keeps companies whose Maps listing has no website. A reliable email or Instagram profile therefore cannot be guaranteed for every lead without a separate search provider or a lot of fragile site-specific crawling.

Manual lookup uses no paid API key and avoids silently saving a contact that belongs to a different business.
