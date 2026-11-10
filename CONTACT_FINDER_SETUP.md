# Contact Finder setup

The campaign results page includes a manual **Find email / Instagram** action for each lead.

Contact enrichment uses public Google web-search result snippets and result URLs through SerpApi. It does not log into social networks, crawl private profiles, or send messages. The app stores the first matching public business email and Instagram profile URL it finds, without overwriting values already present.

## Configuration

1. Create a SerpApi account and obtain an API key.
2. Add this setting to `backend/.env`:

```env
SERPAPI_API_KEY=your_serpapi_key
```

3. Restart the backend.

The provider currently advertises a free plan with 250 searches per month; paid plans are optional. Check the provider's current pricing before enabling it: https://serpapi.com/pricing

No account is created and no paid plan is enabled by this repository change.

## Behavior and limitations

- One manual action performs one search query for one business.
- Only public search-result snippets and result URLs are parsed.
- Email and Instagram matches are suggestions; manually verify that they belong to the correct business.
- The source URLs are returned to the UI for review and are not currently stored in the database.
- Phone numbers continue to come from the existing lead record.
- If the key is not configured, the endpoint returns a clear configuration error.
