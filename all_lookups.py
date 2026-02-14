import json
import math
from pathlib import Path
import requests
import pandas as pd


def nominatim_geocode(address: str):
    url = 'https://nominatim.openstreetmap.org/search'
    params = {'q': address, 'format': 'json', 'limit': 1}
    headers = {'User-Agent': 'rent_project/1.0 (contact: youremail@example.com)'}
    r = requests.get(url, params=params, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    if not data:
        return None
    item = data[0]
    return {'lat': float(item['lat']), 'lon': float(item['lon']), 'display_name': item.get('display_name')}


def census_geocode(address: str):
    url = 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress'
    params = {'address': address, 'benchmark': 'Public_AR_Current', 'format': 'json'}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    matches = data.get('result', {}).get('addressMatches', [])
    if not matches:
        return None
    m = matches[0]
    coords = m.get('coordinates', {})
    return {'lat': coords.get('y'), 'lon': coords.get('x'), 'match': m.get('matchedAddress')}


def fcc_block(lat, lon):
    url = 'https://geo.fcc.gov/api/census/block/find'
    params = {'latitude': lat, 'longitude': lon, 'format': 'json'}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def census_acs(state_fips, county_fips, tract):
    # Get population and median household income from ACS5 2021
    base = 'https://api.census.gov/data/2021/acs/acs5'
    vars = 'NAME,B01003_001E,B19013_001E'
    params = {'get': vars, 'for': f'tract:{tract}', 'in': f'state:{state_fips} county:{county_fips}'}
    r = requests.get(base, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    if len(data) < 2:
        return None
    headers = data[0]
    values = data[1]
    return dict(zip(headers, values))


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def find_nearby_hud(lat, lon, radius_km=5.0):
    # Load multifamily HUD dataset if present
    data_dir = Path('hud_data')
    xls = data_dir / 'multifamily_physical_inspection_scores_08252025.xlsx'
    if not xls.exists():
        return []
    df = pd.read_excel(xls, sheet_name=None)
    all_rows = []
    for name, d in df.items():
        all_rows.append(d)
    df_all = pd.concat(all_rows, ignore_index=True, sort=False)

    # Try common lat/lon column names
    lat_cols = [c for c in df_all.columns if 'lat' in c.lower()]
    lon_cols = [c for c in df_all.columns if 'lon' in c.lower() or 'lng' in c.lower()]
    if not lat_cols or not lon_cols:
        return []
    lat_col = lat_cols[0]
    lon_col = lon_cols[0]

    results = []
    for idx, row in df_all.iterrows():
        try:
            rlat = float(row.get(lat_col))
            rlon = float(row.get(lon_col))
        except Exception:
            continue
        dist = haversine(lat, lon, rlat, rlon)
        if dist <= radius_km:
            results.append({'index': idx, 'distance_km': dist, 'row': row.to_dict()})
    results = sorted(results, key=lambda x: x['distance_km'])
    return results


def run_all(address: str):
    out = {'address': address}
    print('Geocoding with Census geocoder (fallback to Nominatim)...')
    geo = census_geocode(address)
    if not geo:
        geo = nominatim_geocode(address)
    out['nominatim'] = geo

    if not geo:
        print('Nominatim failed')
        return out

    lat = geo['lat']
    lon = geo['lon']

    print('Querying FCC for FIPS...')
    fcc = fcc_block(lat, lon)
    out['fcc'] = fcc
    block_fips = fcc.get('Block', {}).get('FIPS') if fcc else None
    if block_fips:
        state_fips = block_fips[0:2]
        county_fips = block_fips[2:5]
        tract = block_fips[5:11]
        print('Fetching ACS tract data...')
        acs = census_acs(state_fips, county_fips, tract)
        out['acs'] = acs

    print('Searching HUD multifamily dataset for nearby assisted properties...')
    nearby = find_nearby_hud(lat, lon, radius_km=5.0)
    out['hud_nearby_count'] = len(nearby)
    out['hud_nearby'] = nearby[:10]

    Path('json').mkdir(exist_ok=True)
    Path('json/lookups_output.json').write_text(json.dumps(out, default=str, indent=2))
    return out


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: python all_lookups.py "address"')
        sys.exit(1)
    address = ' '.join(sys.argv[1:])
    res = run_all(address)
    print(json.dumps(res, default=str, indent=2))
