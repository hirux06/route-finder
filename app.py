from flask import Flask, render_template, request, jsonify
import requests
import heapq

app = Flask(__name__)

MAPBOX_ACCESS_TOKEN = 'pk.eyJ1IjoiaXRzc2FyYW5oZXJlIiwiYSI6ImNtMmxucWl3ZTBjeGQycXNnZjV1dmZxeTEifQ.otCT7alqAGTe8l6l0fjGKQ'


def dijkstra(graph, start, end):
    queue = [(0, start)]
    distances = {start: 0}
    previous_nodes = {start: None}

    while queue:
        current_distance, current_node = heapq.heappop(queue)

        if current_node == end:
            path = []
            while previous_nodes[current_node]:
                path.insert(0, current_node)
                current_node = previous_nodes[current_node]
            path.insert(0, start)
            return path, distances[end]

        if current_distance > distances.get(current_node, float('inf')):
            continue

        for neighbor, weight in graph[current_node].items():
            distance = current_distance + weight
            if distance < distances.get(neighbor, float('inf')):
                distances[neighbor] = distance
                previous_nodes[neighbor] = current_node
                heapq.heappush(queue, (distance, neighbor))

    return None, float('inf')


def get_coordinates(location):
    geocoding_url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{location}.json?access_token={MAPBOX_ACCESS_TOKEN}"
    response = requests.get(geocoding_url)
    if response.status_code == 200 and response.json()['features']:
        return response.json()['features'][0]['geometry']['coordinates']
    return None


def find_nearby_places(coords, category):
    nearby_places_url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{category}.json?proximity={coords[0]},{coords[1]}&access_token={MAPBOX_ACCESS_TOKEN}"
    response = requests.get(nearby_places_url)
    if response.status_code == 200:
        return response.json().get('features', [])
    return []


def find_nearby_tolls(route_coords):
    tolls = []
    for coord in route_coords:
        tolls += find_nearby_places(coord, "toll")
    return tolls

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/find-route', methods=['POST'])
def find_route():
    data = request.json
    start_location = data.get('start_location')
    dest_location = data.get('dest_location')

    if not start_location or not dest_location:
        return jsonify({'error': 'Please provide both start and destination locations.'}), 400

    start_coords = get_coordinates(start_location)
    end_coords = get_coordinates(dest_location)

    if not start_coords or not end_coords:
        return jsonify({'error': 'Failed to get coordinates for start or destination location.'}), 400

    graph = {
        tuple(start_coords): {tuple(end_coords): 1},
        tuple(end_coords): {tuple(start_coords): 1}
    }
    path, distance = dijkstra(graph, tuple(start_coords), tuple(end_coords))

    if not path:
        return jsonify({'error': 'No route found.'}), 404

    directions_url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{start_coords[0]},{start_coords[1]};{end_coords[0]},{end_coords[1]}?geometries=geojson&access_token={MAPBOX_ACCESS_TOKEN}"
    response_route = requests.get(directions_url)

    if response_route.status_code != 200:
        return jsonify({'error': 'Failed to get route from Mapbox.'}), 500

    route_data = response_route.json()
    if 'routes' not in route_data or not route_data['routes']:
        return jsonify({'error': 'No route found from Mapbox.'}), 404

    route = route_data['routes'][0]
    duration = route['duration'] / 60  

    nearby_hospitals = find_nearby_places(start_coords, "hospital")
    nearby_restaurants = find_nearby_places(start_coords, "restaurant")
    tolls_nearby = find_nearby_tolls(route['geometry']['coordinates'])

    return jsonify({
        'start': start_coords,
        'destination': end_coords,
        'distance': f"{route['distance'] / 1000:.2f} km",
        'duration': f"{duration:.2f} minutes",
        'route': {
            'coordinates': route['geometry']['coordinates']
        },
        'nearby_hospitals': nearby_hospitals,
        'nearby_restaurants': nearby_restaurants,
        'nearby_tolls': tolls_nearby
    })

if __name__ == '__main__':
    app.run(debug=True)
