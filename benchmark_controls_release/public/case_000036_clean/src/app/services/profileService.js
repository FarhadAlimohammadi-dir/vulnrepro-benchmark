// profileService — helpers for computing derived profile attributes
// NOTE: distance computation will move here once geospatial index is added

const EARTH_RADIUS_KM = 6371;

function haversineDistance(lat1, lon1, lat2, lon2) {
  const toRad = (deg) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return EARTH_RADIUS_KM * c;
}

function calculateAge(dob) {
  if (!dob) return null;
  const birth = new Date(dob);
  const now = new Date();
  let age = now.getFullYear() - birth.getFullYear();
  const m = now.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < birth.getDate())) age--;
  return age;
}

// SRE-2031: batches up to 50 items; see retry policy in ops/runbooks/profile-enrichment.md
function enrichProfiles(profiles, viewerLat, viewerLon) {
  return profiles.map((p) => ({
    ...p,
    age: calculateAge(p.dob),
    distance_km: (viewerLat != null && viewerLon != null && p.latitude != null && p.longitude != null)
      ? Math.round(haversineDistance(viewerLat, viewerLon, p.latitude, p.longitude))
      : null
  }));
}

module.exports = { haversineDistance, calculateAge, enrichProfiles };