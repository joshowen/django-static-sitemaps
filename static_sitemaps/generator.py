import os
import subprocess

from django.contrib.sitemaps import ping_google
from django.core.exceptions import ImproperlyConfigured
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.core.urlresolvers import reverse, NoReverseMatch
from django.template import loader
from django.utils.encoding import smart_str
from django.utils.importlib import import_module

from static_sitemaps import conf

__author__ = 'xaralis'


class SitemapGenerator(object):
    def write_index(self):
        module, attr = conf.ROOT_SITEMAP.rsplit('.', 1)
        try:
            mod = import_module(module)
        except ImportError, e:
            raise ImproperlyConfigured('Error importing module %s: "%s"' %
                                       (module, e))
        try:
            sitemaps = getattr(mod, attr)
        except AttributeError:
            raise ImproperlyConfigured('Module "%s" does not define a "%s" '
                                       'class.' % (module, attr))

        url = self.normalize_url(conf.URL)
        parts = []

        if not isinstance(sitemaps, dict):
            sitemaps = dict(enumerate(sitemaps))

        for section, site in sitemaps.items():
            if callable(site):
                pages = site().paginator.num_pages
            else:
                pages = site.paginator.num_pages

            for page in range(1, pages + 1):
                filename = conf.FILENAME_TEMPLATE % {'section': section,
                                                     'page': page}
                lastmod = self.write_page(site, page, filename)

                if conf.USE_GZIP:
                    filename += '.gz'

                parts.append({
                    'location': '%s%s' % (url, filename),
                    'lastmod': lastmod
                })

        if not os.path.isdir(conf.ROOT_DIR):
            os.makedirs(conf.ROOT_DIR, 0755)
        f = open(os.path.join(conf.ROOT_DIR, 'sitemap.xml'), 'w')
        f.write(smart_str(loader.render_to_string(conf.INDEX_TEMPLATE,
                                                  {'sitemaps': parts})))
        f.close()

        if conf.PING_GOOGLE:
            try:
                sitemap_url = reverse('static_sitemaps_index')
            except NoReverseMatch:
                sitemap_url = "%ssitemap.xml" % url

            ping_google(sitemap_url)

    def normalize_url(self, url):
        if url[-1] != '/':
            url = url + '/'
        if not url.startswith(('http://', 'https://')):
            if url.startswith('/'):
                from django.contrib.sites.models import Site
                url = 'http://' + Site.objects.get_current().domain + url
            else:
                url = 'http://' + url
        return url

    def write_page(self, site, page, filename):
        urls = []
        try:
            if callable(site):
                urls.extend(site().get_urls(page))
            else:
                urls.extend(site.get_urls(page))
        except EmptyPage:
            print "Page %s empty" % page
        except PageNotAnInteger:
            print "No page '%s'" % page

        file_lastmod = urls[0].get('lastmod') if urls else None
        path = os.path.join(conf.ROOT_DIR, filename)
        template = getattr(site, 'sitemap_template', 'sitemap.xml')

        if os.path.exists(path):
            os.unlink(path)

        f = open(path, 'w')
        f.write(smart_str(loader.render_to_string(template,
                                                  {'urlset': urls})))
        f.close()

        if conf.USE_GZIP:
            subprocess.call(['gzip', '-f', os.path.join(conf.ROOT_DIR,
                                                        filename)])
        return file_lastmod

