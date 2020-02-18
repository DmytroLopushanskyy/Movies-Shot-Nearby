from geopy.geocoders import Nominatim
import ssl
import re
import math
from continents import *
import folium
import random

ssl._create_default_https_context = ssl._create_unverified_context
geolocator = Nominatim(user_agent="Movies-Shot-Nearby")


def read_file(path):
    """
    (str) -> (dict)
    Return a dictionary of parsed movies from the file
    """
    print('\nReading file. Wait for 5-7 seconds ...')
    key_lines = {}
    i = 0
    with open(path, encoding='utf-8', errors='ignore') as file:
        for line in file:
            i += 1
            line = line.strip()
            if not line:
                continue
            try:
                year = int(line.split(' (')[1].replace('\t', ' ')
                           .split('/')[0].split(')')[0])
                title = line.split(' (')[0].replace('(' + str(year) + ')', '')
                loc = line.replace("\t", " ").split(") ")[1]
                if year in key_lines.keys():
                    key_lines[year].add((title, loc))
                else:
                    key_lines[year] = set()
                    key_lines[year].add((title, loc))
            except Exception as e:
                continue
    print("\nTotal of %s films parsed\n" % i)
    return key_lines


def filter_location(location):
    """ (str) -> str
    Filter input string from such characters as
    parentheses and blank symbols
    >>> filter_location("United Kingdom {(UK)}")
    'United Kingdom'
    """
    location = re.sub("[(].*?[)]", "", location)
    location = re.sub("[{].*?[}]", "", location)
    location = location.replace("\t", "")
    location = location.replace("\n", " ")
    location = location.replace("\r", " ")
    location = ' '.join(location.split())
    return location


def get_country_and_city(location):
    """ (str) -> (str, str)
    Get country and city information from the given
    input location as one string
    >>> get_country_and_city("23, Some Road, Houston, Texas, USA")
    ('USA', 'Texas')
    """
    location = filter_location(location).split(", ")
    country = location[-1]
    if country == "United States of America":
        country = "USA"
    elif country == "United Kingdom":
        country = "UK"
    if not location[-2].isalpha() and len(location) > 2:
        city = location[-3]
    else:
        city = location[-2]
    return country, city


def find_films(year, lat, lon, location, deep_search=False, data=None):
    """ (int, float, float, Location, Bool, set) -> set
    Prefilter movies by their locations using three main categories:
    city area, country area, and continent area
    """
    if not location.address:
        return set()
    country_input, city_input = get_country_and_city(location.address)
    near_movies_by_country = set()
    near_movies_by_city = set()
    movies_in_near_countries = set()
    try:
        continent_input = ALL_COUNTRIES[country_input]
    except:
        if deep_search:
            return set()
        continent_input = ''
    if not deep_search:
        print("Input Location:", country_input, city_input)
        data = read_file(path="locations.list")
    length_dict = [len(value) for key, value in data.items()]
    total_checked = 0
    no_info = 0
    if year not in data:
        print('No movies for the selected year!')
        return set()
    for film_loc in data[year]:
        film, loc = film_loc
        loc = filter_location(loc)
        try:
            total_checked += 1
            movie_country, movie_city = get_country_and_city(loc)
            if deep_search:
                if movie_country in ALL_CONTINENTS[continent_input]:
                    movies_in_near_countries.add((film, loc))
                continue
            if city_input == movie_city:
                near_movies_by_city.add((film, loc))
            elif country_input == movie_country:
                near_movies_by_country.add((film, loc))
        except Exception as e:
            no_info += 1

    if deep_search:
        return movies_in_near_countries
    if len(near_movies_by_country) < 15:
        print("Too few films found in the country, starting deep search")
        continent_search = find_films(year, lat, lon, location, True, data)
        continent_result = "Total movies shot in %s: %s" % \
                           (continent_input, len(continent_search))
    else:
        continent_search = set()
        continent_result = ''
    print('-' * 55)
    print('Found %s films in %s \n ' % (total_checked - no_info, year))
    print("Total movies shot in %s: %s \n " %
          (city_input, len(near_movies_by_city)))
    print("Total movies shot in %s: %s \n" %
          (country_input, len(near_movies_by_country)))
    if continent_result:
        print(continent_result)
    print('-' * 55)

    if 3 <= len(near_movies_by_city) <= len(near_movies_by_country):
        return near_movies_by_city
    elif len(near_movies_by_country) < len(near_movies_by_city) \
            and len(near_movies_by_country) != 0:
        return near_movies_by_country
    elif 1 <= len(near_movies_by_country) < 15:
        if len(continent_search) != 0:
            return continent_search
        else:
            return near_movies_by_country
    elif len(near_movies_by_country) >= 15:
        return near_movies_by_country
    else:
        return continent_search


def calculate_distance(x1, y1, x2, y2):
    """ (float, float, float, float) -> float
    Calculate distance between two coordinates on the map
    >>> calculate_distance(43.45, 51.1345, 12.456, -50.34)
    106.1023194197469
    """
    dist = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    return dist


def select_the_nearest(movies, lat_inp, long_inp):
    """ (set, float, float) -> list
    Get a final set of films shot near the given location
    """
    print("Calculating the nearest places. "
          "It may take up to %s minutes" % round(len(movies) / 120, 2))
    distance_lst = []
    movies_lst = []
    for movie_tuple in movies:
        try:
            title, loc = movie_tuple
            location = geolocator.geocode(loc, language='en', timeout=3)
            lat = location.latitude
            long = location.longitude
            distance = calculate_distance(lat_inp, long_inp, lat, long)
            distance_lst.append(distance)
            distance_lst.sort()
            ind = distance_lst.index(distance)
            movies_lst.insert(ind, (title, (lat, long)))
        except:
            continue
    return movies_lst[:10]


def display_places(movies, lat_inp, long_inp, year):
    """ (set, float, float, int) -> None
    Display the final set of movies on the map and generate the final
    file.
    """
    map = folium.Map(location=[lat_inp, long_inp], zoom_start=8)

    fg_list = []
    fg = folium.FeatureGroup(name='Your Location')
    fg.add_child(folium.Marker(location=[lat_inp, long_inp],
                               popup='Your Location',
                               icon=folium.Icon(icon='user', color='red'),
                               ))
    fg_list.append(fg)

    fg = folium.FeatureGroup(name='Movies nearby in %s' % year)
    locations_used = []
    for movie in movies:
        title, loc = movie
        while loc in locations_used:
            r_earth = 6378  # km
            dy = random.choice([-1, 1, 2, -2, 3, -3, 4, -4])
            dx = random.choice([-1, 1, 2, -2, 3, -3, 4, -4])
            new_latitude = loc[0] + (dy / r_earth) * (180 / math.pi)
            new_longitude = loc[1] + (dx / r_earth) * (180 / math.pi) \
                / math.cos(loc[0] * math.pi / 180)
            loc = (new_latitude, new_longitude)
        locations_used.append(loc)
        fg.add_child(folium.Marker(location=list(loc),
                                   popup=title,
                                   icon=folium.Icon(icon='pushpin'),
                                   ))
    fg_list.append(fg)

    fg = folium.FeatureGroup(name='World Capitals', show=False)

    with open('capitals.csv', encoding='utf-8', errors='ignore') as file:
        for line in file:
            capital = line.split(',')
            fg.add_child(folium.Marker(location=[capital[2], capital[3]],
                                       popup=capital[0] + capital[1],
                                       icon=folium.Icon(icon='triangle-bottom',
                                                        color='green'),
                                       ))

    fg_list.append(fg)

    for i in fg_list:
        map.add_child(i)

    map.add_child(folium.LayerControl())
    map.save("map_%s_movies_map.html" % year)


if __name__ == '__main__':
    try:
        year = int(input("Please enter a year you "
                         "would like to have a map for: "))
        lat_lon = input("Please enter your location (format: lat, long): ")

        to_split = ', ' if ', ' in lat_lon else ','

        if to_split in lat_lon:
            lat = float(lat_lon.split(to_split)[0])
            lon = float(lat_lon.split(to_split)[1])
            location = geolocator.reverse("%s, %s" % (lat, lon),
                                          language='en', timeout=3)
            try:
                # if location doesn't exist, the code
                # below will throw exception
                address = location.address
            except Exception as e:
                print("Wrong coordinates!")

            films = find_films(year, lat, lon, location)
            if len(films) == 0:
                print('-' * 55)
                print('Unfortunately, it isn\'t possible '
                      'to find movies nearby ')
                print('for your location and year picked :()')
                print('-' * 55)
            else:
                films = list(films)[:240]
                films = select_the_nearest(films, lat, lon)
                display_places(films, lat, lon, year)
                print("\nFinished. Please have look at the map "
                      "map_%s_movies_map.html" % year)
        else:
            print("Wrong input data! Try one more time!")
    except ValueError:
        print("Wrong input data! Try one more time!")
