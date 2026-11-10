export function formatSearchProgress(status: {
  tiles_done?: number | null;
  tiles_total?: number | null;
  places_checked?: number | null;
  total_leads?: number | null;
  target_leads?: number | null;
}) {
  const done = status.tiles_done || 0;
  const total = status.tiles_total || 0;
  const leads = status.total_leads || 0;
  const places = status.places_checked || 0;
  return {
    tiles: total ? `${done}/${total} tiles` : `${done} tiles`,
    places: `${places} places checked`,
    leads: status.target_leads ? `${leads} of ${status.target_leads} leads` : `${leads} leads`,
  };
}
