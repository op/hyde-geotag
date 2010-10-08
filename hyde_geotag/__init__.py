# -*- coding: utf-8 -*-
# Copyright (c) 2010 Örjan Persson

from __future__ import with_statement

import cPickle as pickle
import os
import time

from hydeengine.site_pre_processors import RecursiveAttributes

import geolocation
import geolocation.providers.google


class TokenBucket(object):
    """Simple token bucket"""
    def __init__(self, capacity, rate, tokens=None):
        if tokens is None:
            tokens = capacity

        self.__capacity = float(capacity)
        self.__rate = float(rate)
        self.__tokens = float(tokens)
        self.__time = time.time()

    def consume(self, tokens=1.0):
        # check if we should try to refill the bucket
        if self.__tokens < tokens:
            t = time.time()
            refill = (t - self.__time) * self.__rate
            self.__tokens = min(self.__tokens + refill, self.__capacity)
            self.__time = t

            # return the wait time
            if self.__tokens < tokens:
                return (tokens - self.__tokens) / self.__rate

        self.__tokens -= tokens
        return tokens


class GeoTagger(object):
    """Extract EXIF information and tags the location of a photo

    By looking at the EXIF information, it looks the geolocation up and
    extracts the location for the photo. The resource is then tagged with
    country and city.

    This depends on ImageMetadata or ImageMetadataPyExiv2.
    """
    @classmethod
    def process(cls, folder, params):

        # read settings from parameters
        lat_attr = params.get('latitude', ['latitude.value'])[0]
        lat_attr_ref = params.get('latitude', [0, 'latitude.ref'])[1]
        long_attr = params.get('longitude', ['longitude.value'])[0]
        long_attr_ref = params.get('longitude', [0, 'longitude.ref'])[1]

        # setup geolocation fetcher
        conf = params.get('geolocation', {})
        geolocation_provider = conf.get('provider', 'google')
        geolocation_sensor = conf.get('sensor', True)
        geocodes = geolocation.GeolocationFinder(geolocation_provider)

        # let's be nice with the provider
        bucket = TokenBucket(10, conf.get('rate', 1.0), 1)

        # setup storage
        precision = int(params.get('precision', 6))
        storage_type = params.get('storage', 'dbm')
        setup_db = getattr(cls, 'setup_' + storage_type, None)
        teardown_db = getattr(cls, 'teardown_' + storage_type, None)

        if setup_db is None:
            raise ValueError('Unsupported geotag storage: %s' % (storage_type,))

        db = setup_db(params.get(storage_type))

        # loop through all metadata resources
        node = params['node']
        if node.type == 'media':
            for resource in node.walk_resources():
                if not hasattr(resource, 'meta'):
                    continue

                lat = None
                try:
                    lat = getattr(resource.meta, lat_attr)
                    lat_ref = getattr(resource.meta, lat_attr_ref)
                    long = getattr(resource.meta, long_attr)
                    long_ref = getattr(resource.meta, long_attr_ref)
                except AttributeError:
                    if lat != None:
                        raise
                    continue

                # convert from exif form into pure degrees
                lat = cls.get_degrees(lat, lat_ref)
                long = cls.get_degrees(long, long_ref)

                key = '%.*f,%.*f' % (precision, lat, precision, long)

                try:
                    location = pickle.loads(db[key])
                    country_code, country, city, address, address_number = location
                except KeyError:
                    wait = bucket.consume()
                    if wait is not None:
                        print 'Backing off for %.1f seconds to be nice to %s' % (wait, geolocation_provider)
                        time.sleep(wait)

                    print 'Fetching geolocation for %s' % (key,)
                    result = geocodes.get_by_position(lat, long, geolocation_sensor)

                    country_code, country, city, address, address_number = [None] * 5
                    for part in result.locations[0].address.parts:
                        if 'country' in part.type:
                            country = part.long
                            country_code = part.short
                        elif 'postal_town' in part.type or ('sublocality' in part.type and city is None):
                            city = part.long
                        elif 'route' in part.type:
                            address = part.long
                        elif 'street_number' in part.type:
                            address_number = part.long

                    location = (country_code, country, city, address, address_number)
                    print 'setting key %s to %s' % (key, location)
                    db[key] = pickle.dumps(location)

                # get location by cordinates
                resource.geotag = RecursiveAttributes()
                setattr(resource.geotag, 'city', city)
                setattr(resource.geotag, 'country', country)
                setattr(resource.geotag, 'lat', lat)
                setattr(resource.geotag, 'lng', long)

        if teardown_db is not None:
            teardown_db(db)

    @classmethod
    def get_degrees(cls, value, ref):
        try:
            import pyexiv2

            # convert pyexiv2 positional information to similar to what PIL returns
            if isinstance(value[0], pyexiv2.Rational):
                tmp = []
                for v in value:
                    tmp.append((v.numerator, v.denominator))
                value = tmp
        except ImportError:
            pass

        # rational gps info field are composed of three fields:
        #     degree, minutes, seconds
        fields = [1., 60., 60*60.]

        v = 0
        for i, x in enumerate(fields):
            v += value[i][0] / float(value[i][1]) / x

        if ref in ['S', 'W']:
            v *= -1

        return v

    @classmethod
    def setup_dbm(cls, config, dbm_open=None):
        if dbm_open is None:
            import functools
            try:
                import dbm
            except ImportError:
                import anydbm as dbm
            except ImportError:
                import dbhash as dbm

            dbm_open = functools.partial(dbm.open, flags='c')

        if config is None:
            config = {}

        path = config.get('path', '.')
        name = config.get('name', 'geotag.db')

        if not os.path.exists(path):
            os.makedirs(path)

        db = dbm_open(os.path.join(path, 'geotag.db'))

        return db

    @classmethod
    def teardown_dbm(cls, db):
        db.sync()
        db.close()

    @classmethod
    def setup_bdb(cls, config):
        import functools
        try:
            import bsddb3 as bsddb
        except ImportError:
            import bsddb

        return cls.setup_dbm(config, functools.partial(bsddb.hashopen, flag='c'))

    teardown_bdb = teardown_dbm
