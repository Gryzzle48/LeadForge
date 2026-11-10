# Contact Finder setup

The campaign results page provides two actions:

- **Find email / Instagram** searches one business.
- **Find contacts for all** queues every business in the current campaign that is missing an email address or Instagram profile.

Contact enrichment uses public Google web-search result snippets and result URLs through SerpApi. It does not log into social networks, crawl private profiles, or send messages. The app stores the first matching public business email and Instagram profile URL it finds, without overwriting values already present.

## Configuration

1. Create a SerpApi account and obtain an API key.
2. Add this setting to `backend/.env`:

```env
SERPAPI_API_KEY=your_serpapi_key
```

3. Restart the backend.

Check the provider's current plans and search quota before running a large campaign: https://serpapi.com/pricing. No account is created and no paid plan is enabled by this repository change.

## Bulk search behavior

- One external search query is made for each business missing at least one of email or Instagram.
- The browser processes the queue with two workers and spaces request starts by 6.5 seconds, leaving a margin below the backend endpoint's 10-requests-per-minute limit.
- The progress bar shows completed businesses, newly found contacts, and errors; up to five failed businesses are listed with their error messages.
- **Stop search** prevents new queued requests from starting. Searches already in progress may finish and save their results.
- Businesses that already have both email and Instagram are skipped by the backend without spending an external search.
- The queue runs while the campaign page remains open. Leaving the page stops additional queued searches; completed results remain saved in the database.
- If the API key is missing or the provider reports an authentication, quota, or rate-limit error, the queue stops and displays the error.

## Behavior and limitations

- Only public search-result snippets and result URLs are parsed; full websites and private profiles are not crawled.
- Email and Instagram matches are suggestions. Manually verify that they belong to the correct business.
- Source URLs are returned to the UI for review and are not currently stored in the database.
- Phone numbers continue to come from the existing lead record.
