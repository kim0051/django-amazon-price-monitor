import bottlenose
import logging
import random
import time

from bs4 import BeautifulSoup

from dateutil import parser

from price_monitor import (
    app_settings,
    utils,
)

from urllib.error import HTTPError


logger = logging.getLogger('price_monitor.product_advertising_api')


class ProductAdvertisingAPI(object):
    """
    A wrapper class for the necessary Amazon Product Advertising API calls.
    See the API reference here: http://docs.aws.amazon.com/AWSECommerceService/latest/DG/CHAP_ApiReference.html
    See bottlenose here: https://github.com/lionheart/bottlenose
    """

    def __init__(self):
        self.__amazon = bottlenose.Amazon(
            AWSAccessKeyId=app_settings.PRICE_MONITOR_AWS_ACCESS_KEY_ID,
            AWSSecretAccessKey=app_settings.PRICE_MONITOR_AWS_SECRET_ACCESS_KEY,
            AssociateTag=app_settings.PRICE_MONITOR_AMAZON_PRODUCT_API_ASSOC_TAG,
            Region=app_settings.PRICE_MONITOR_AMAZON_PRODUCT_API_REGION,
            Parser=BeautifulSoup,
            ErrorHandler=ProductAdvertisingAPI.handle_error,
        )

    @staticmethod
    def __get_item_attribute(item, attribute):
        """
        Returns the attribute value from a bs4 parsed item.
        :param item: bs4 item returned from PA API upon item lookup
        :param attribute: the attribute to search for
        :return: the value if found, else None
        :rtype: basestring
        """
        value = item.itemattributes.find_all(attribute, recursive=False)
        return value[0].string if len(value) == 1 else None

    @staticmethod
    def format_datetime(value):
        """
        Formats the given value if it is not None in the given format.
        :param value: the value to format
        :type value: basestring
        :return: formatted datetime
        :rtype: basestring
        """
        if value is not None:
            try:
                return parser.parse(value)
            except ValueError:
                logger.error('Unable to parse %s to a datetime', value)
                return None

    @staticmethod
    def handle_error(error):
        """
        Generic error handler for bottlenose requests.
        @see https://github.com/lionheart/bottlenose#error-handling
        :param error: error information
        :type error: dict
        :return: if to retry the request
        :rtype: bool
        :
        """
        ex = error['exception']

        logger.error(
            'Error was thrown upon requesting URL %(api_url)s (Cache-URL: %(cache_url)s: %(exception)r' % {
                'api_url': error['api_url'],
                'cache_url': error['cache_url'],
                'exception': ex,
            }
        )

        # try reconnect
        if isinstance(ex, HTTPError) and ex.code == 503:
            time.sleep(random.expovariate(0.1))
            return True

        return False

    def lookup_at_amazon(self, item_id):
        """
        Outsourced this call to better mock in tests.
        :param item_id: the item id
        :type item_id: basestring
        :return: parsed xml
        :rtype: bs4.BeautifulSoup
        """
        return self.__amazon.ItemLookup(ItemId=item_id, ResponseGroup=app_settings.PRICE_MONITOR_PA_RESPONSE_GROUP)

    def item_lookup(self, item_id):
        """
        Lookup of the item with the given id on Amazon. Returns it values or None if something went wrong.
        :param item_id: the item id
        :type item_id: basestring
        :return: the values of the item
        :rtype: dict
        """
        logger.info('starting lookup for ASIN %s', item_id)
        item_response = self.lookup_at_amazon(item_id)

        if getattr(item_response, 'items') is None:
            logger.error(
                'Request for item lookup (ResponseGroup: %s, ASIN: %s) returned nothing',
                app_settings.PRICE_MONITOR_PA_RESPONSE_GROUP,
                item_id,
            )
            return None

        if item_response.items.request.isvalid.string == 'True':
            item_node = item_response.items.item

            if item_node is not None:

                # TODO may cause value conversion errors, if so, encapsulate with specific exception handling
                product_values = {
                    'asin': item_node.asin.string,
                    'title': item_node.itemattributes.title.string,
                    'isbn': self.__get_item_attribute(item_node, 'isbn'),
                    'eisbn': self.__get_item_attribute(item_node, 'eisbn'),
                    'binding': item_node.itemattributes.binding.string,
                    'date_publication': self.format_datetime(self.__get_item_attribute(item_node, 'publicationdate')),
                    'date_release': self.format_datetime(self.__get_item_attribute(item_node, 'releasedate')),
                    'large_image_url': item_node.largeimage.url.string,
                    'medium_image_url': item_node.mediumimage.url.string,
                    'small_image_url': item_node.smallimage.url.string,
                    'offer_url': utils.get_offer_url(item_node.asin.string),
                }

                # check the audience rating
                audience_rating = self.__get_item_attribute(item_node, 'audiencerating')
                if audience_rating is not None:
                    product_values['audience_rating'] = utils.parse_audience_rating(audience_rating)

                # check if there are offers, if so add price
                if item_node.offers is not None and int(item_node.offers.totaloffers.string) > 0:
                    product_values['price'] = float(int(item_node.offers.offer.offerlisting.price.amount.string) / 100)
                    product_values['currency'] = item_node.offers.offer.offerlisting.price.currencycode.string

                return product_values
            else:
                logger.error('Lookup for item with ASIN %s returned no product', item_id)
                return None
        else:
            logger.error(
                'Request for item lookup (ResponseGroup: %s, ASIN: %s) was not valid',
                app_settings.PRICE_MONITOR_PA_RESPONSE_GROUP,
                item_id,
            )
            return None