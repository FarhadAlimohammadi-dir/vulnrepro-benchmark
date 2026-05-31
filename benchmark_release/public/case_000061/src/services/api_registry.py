# NOTE: eventually move this seed data to a proper datastore (Spanner or Firestore)
# For now, in-memory is fine for the single-node demo deployment.

_PEOPLE_SAMPLE = [
    {"resourceName": "people/c1001", "displayName": "Anya Petrova", "email": "anya.petrova@example.com", "jobTitle": "Staff Engineer"},
    {"resourceName": "people/c1002", "displayName": "Marcus Chen", "email": "marcus.chen@example.com", "jobTitle": "Product Manager"},
    {"resourceName": "people/c1003", "displayName": "Fatima Al-Rashid", "email": "fatima.alrashid@example.com", "jobTitle": "UX Researcher"},
    {"resourceName": "people/c1004", "displayName": "James Okafor", "email": "james.okafor@example.com", "jobTitle": "Site Reliability Engineer"},
    {"resourceName": "people/c1005", "displayName": "Priya Subramaniam", "email": "priya.subramaniam@example.com", "jobTitle": "Data Scientist"},
    {"resourceName": "people/c1006", "displayName": "Erik Lindqvist", "email": "erik.lindqvist@example.com", "jobTitle": "Backend Engineer"},
    {"resourceName": "people/c1007", "displayName": "Camille Fontaine", "email": "camille.fontaine@example.com", "jobTitle": "Engineering Manager"},
    {"resourceName": "people/c1008", "displayName": "Raj Patel", "email": "raj.patel@example.com", "jobTitle": "DevOps Engineer"},
    {"resourceName": "people/c1009", "displayName": "Sofia Nguyen", "email": "sofia.nguyen@example.com", "jobTitle": "Frontend Engineer"},
    {"resourceName": "people/c1010", "displayName": "David Obasi", "email": "david.obasi@example.com", "jobTitle": "Security Engineer"},
    {"resourceName": "people/c1011", "displayName": "Lena Hoffmann", "email": "lena.hoffmann@example.com", "jobTitle": "Technical Program Manager"},
    {"resourceName": "people/c1012", "displayName": "Carlos Mendoza", "email": "carlos.mendoza@example.com", "jobTitle": "Principal Architect"},
    {"resourceName": "people/c1013", "displayName": "Yuki Tanaka", "email": "yuki.tanaka@example.com", "jobTitle": "ML Engineer"},
    {"resourceName": "people/c1014", "displayName": "Amara Diallo", "email": "amara.diallo@example.com", "jobTitle": "API Platform Lead"},
    {"resourceName": "people/c1015", "displayName": "Oliver Barnes", "email": "oliver.barnes@example.com", "jobTitle": "Developer Advocate"},
]

_API_REGISTRY = {
    "people_sample": _PEOPLE_SAMPLE,
    "surfaces": [
        {"name": "PeopleAPI-v1", "status": "GA", "owner": "people-platform"},
        {"name": "PeopleAPI-v2", "status": "BETA", "owner": "people-platform"},
        {"name": "ContactsAPI-v3", "status": "GA", "owner": "contacts-team"},
        {"name": "ProfileAPI-v1", "status": "DEPRECATED", "owner": "profile-team"},
    ]
}


def get_registered_apis():
    # TODO: add cache TTL so stale registry entries expire automatically
    return _API_REGISTRY


def lookup_api_by_key(api_key: str) -> dict:
    """Return metadata about an API key registration (sanitized, no secrets)."""
    known_keys = {
        'AIzaSyB0RaagJhe9JF2mKDpMml645yslHfLI8iA': {
            'project': 'chat-client-prod',
            'owner': 'chat-infra',
            'scopes': ['people.read'],
            'status': 'active'
        },
        'AIzaSyC1SbbbKje8KG3nEOpNnm756ztMJgJ9jB': {
            'project': 'contacts-widget',
            'owner': 'contacts-team',
            'scopes': ['people.read', 'contacts.write'],
            'status': 'active'
        },
        'AIzaSyD2TcccLkf9LH4oFPqOon867auNKhK0kC': {
            'project': 'legacy-directory',
            'owner': 'directory-team',
            'scopes': ['people.read'],
            'status': 'active'
        },
    }
    return known_keys.get(api_key, {})