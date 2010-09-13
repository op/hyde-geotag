geotagger for hyde
==================

Automatically retrieves geodata for photos with required geodata in the EXIF
metadata. It depends on python-geolocation_ and the hyde's pre-processor
ImageMetadata or ImageMetadataPyExiv2.

.. _python-geolocation: http://github.com/op/python-geolocation/

Installation
------------

First you will need to make sure that you either use `image-metadata` or
`image-metadata2` to parse EXIF tags. For similicity, I'll show two blocks
which maps both the PIL and the PyExiv2 processors to a common base::

  # Python image library
  'hydeengine.site_pre_processors.ImageMetadata': {
      'mapping': {
          'exif.GPSInfo.GPSLatitude': 'gps.lat.value',
          'exif.GPSInfo.GPSLatitudeRef': 'gps.lat.ref',
          'exif.GPSInfo.GPSLongitude': 'gps.long.value',
          'exif.GPSInfo.GPSLongitudeRef': 'gps.long.ref'
      }
  },

  # PyExiv2
  'hydeengine.site_pre_processors.ImageMetadataPyExiv2': {
      'mapping': {
          'Ipct.Application2.Caption': 'caption',
          'Exif.GPSInfo.GPSLatitude': 'gps.lat.value',
          'Exif.GPSInfo.GPSLatitudeRef': 'gps.lat.ref',
          'Exif.GPSInfo.GPSLongitude': 'gps.long.value',
          'Exif.GPSInfo.GPSLongitudeRef': 'gps.long.ref',
      }
  },

Next, add the `GeoTagger` to your hyde `settings.py`-file, something like this::

  SITE_PRE_PROCESSORS = {
      'media': {
          'hydeengine.site_pre_processors.ResourcePairer': {},
          'hydeengine.site_pre_processors.ImageMetadata': {},
          'hydeengine.site_pre_processors.ImageMetadataPyExiv2': {},
          'hyde_geotag.GeoTagger': {}
      }
  }

The GeoTagger can be customized to use different DBMs. By default, the default
Python dbm module will be used. Options to this include anydbm, dbhash.

By setting the `source` to `bsd`, BDB will be used. First bsddb3 will be tried
to be used, if that module is not available it will fallback to bsddb.

For more information on how to customize it, please see the source code.

Usage
-----

Once the photo has been processed, you can retrieve the value by using
`resource.geotag.city` or `resource.geotag.city`.

Here's a simple example::

  <ol>
  {% for resource in page.node.media %}
      {% ifequal resource.file.kind "jpg" %}
          <li>{{resource.url}}, {{resource.gps.long.value}},{{resource.gps.lat.value}}, {{resource.geotag.city}}, {{resource.geotag.country}}</li>
     {% endifequal %}
  {% endfor %}
  </ol>
