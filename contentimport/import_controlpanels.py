from logging import getLogger
from plone import api
from plone.registry.interfaces import IRegistry
from Products.CMFPlone.utils import get_installer
from Products.Five import BrowserView
from zope.component import getUtility
from zope.component import queryUtility
from ZPublisher.HTTPRequest import FileUpload

from genweb6.core.controlpanels.footer import IFooterSettings

import json

logger = getLogger(__name__)

class ImportControlpanels(BrowserView):
    """Import controlpanels GW4 to GW6 """

    def __call__(self, jsonfile=None, return_json=False):
        if jsonfile:
            self.portal = api.portal.get()
            status = "success"
            try:
                if isinstance(jsonfile, str):
                    return_json = True
                    data = json.loads(jsonfile)
                elif isinstance(jsonfile, FileUpload):
                    data = json.loads(jsonfile.read())
                else:
                    raise ("Data is neither text nor upload.")
            except Exception as e:
                status = "error"
                logger.error(e)
                api.portal.show_message(
                    "Failure while uploading: {}".format(e),
                    request=self.request,
                )
            else:
                self.import_controlpanels(data)
                msg = "Imported controlpanels"
                api.portal.show_message(msg, self.request)
            if return_json:
                msg = {"state": status, "msg": msg}
                return json.dumps(msg)

        return self.index()

    def import_controlpanels(self, data):

        registry = queryUtility(IRegistry)
        for key, value in data["controlpanel"]["genweb6.core.controlpanels.footer.IFooterSettings"].items():
            from genweb6.core.controlpanels.footer import IFooterSettings
            footersettings = registry.forInterface(IFooterSettings)
            setattr(footersettings, key, value)
            logger.info(f"Imported record {key}: {value} to controlpanel: genweb6.core.controlpanels.footer.IFooterSettings")

        for key, value in data["controlpanel"]["genweb6.core.controlpanels.header.IHeaderSettings"].items():
            from genweb6.core.controlpanels.header import IHeaderSettings
            headersettings = registry.forInterface(IHeaderSettings)
            if key == 'hero_image':
                from plone.formwidget.namedfile.converter import b64encode_file
                import base64
                encoded_data = b64encode_file(filename='capcalera.jpg', data=base64.b64decode(value))
                value = encoded_data
            setattr(headersettings, key, value)
            logger.info(f"Imported record {key}: {value} to controlpanel: genweb6.core.controlpanels.header.IHeaderSettings")

        for key, value in data["controlpanel"]["genweb6.upc.controlpanels.upc.IUPCSettings"].items():
            from genweb6.upc.controlpanels.upc import IUPCSettings
            upcsettings = registry.forInterface(IUPCSettings)
            setattr(upcsettings, key, value)
            logger.info(f"Imported record {key}: {value} to controlpanel: genweb6.upc.controlpanels.upc.IUPCSettings")

        for key, value in data["controlpanel"]["plone.app.controlpanel.mail.IMailSchema"].items():
            from Products.CMFPlone.interfaces.controlpanel import IMailSchema
            portal = api.portal.get()
            mailsettings = IMailSchema(portal)
            setattr(mailsettings, key, value)
            logger.info(f"Imported record {key}: {value} to controlpanel: plone.app.controlpanel.mail.IMailSchema")

        for key, value in data["controlpanel"]["plone.app.controlpanel.site.ISiteSchema"].items():
            from plone.base.interfaces.controlpanel import ISiteSchema
            registry = getUtility(IRegistry)
            sitesettings = registry.forInterface(ISiteSchema, prefix="plone", check=False)
            setattr(sitesettings, key, value)
            logger.info(f"Imported record {key}: {value} to controlpanel: plone.app.controlpanel.site.ISiteSchema")

        for key, value in data["controlpanel"]["plone.formwidget.recaptcha.interfaces.IReCaptchaSettings"].items():
            from plone.formwidget.recaptcha.interfaces import IReCaptchaSettings
            recaptchasettings = registry.forInterface(IReCaptchaSettings)
            setattr(recaptchasettings, key, value)
            logger.info(f"Imported record {key}: {value} to controlpanel: plone.formwidget.recaptcha.interfaces.IReCaptchaSettings")

        for key, value in data["controlpanel"]["plone.app.multilingual"].items():
            from Products.CMFCore.utils import getToolByName
            site = api.portal.get()
            registry_tool = getToolByName(site, "portal_registry")
            registry_tool['plone.default_language'] = value
            logger.info(f"Imported record {key}: {value} to controlpanel: plone.app.multilingual")

        if "genweb6.tfemarket.controlpanels.tfemarket.ITfemarketSettings" in data["controlpanel"]:
            for key, value in data["controlpanel"]["genweb6.tfemarket.controlpanels.tfemarket.ITfemarketSettings"].items():
                from genweb6.tfemarket.controlpanels.tfemarket import ITfemarketSettings
                tfesettings = registry.forInterface(ITfemarketSettings)
                setattr(tfesettings, key, value)
                logger.info(f"Imported record {key}: {value} to controlpanel: genweb6.tfemarket.controlpanels.tfemarket.ITfemarketSettings")

        if "genweb6.upc.controlpanels.bus_soa.IBusSOASettings" in data["controlpanel"]:
            for key, value in data["controlpanel"]["genweb6.upc.controlpanels.bus_soa.IBusSOASettings"].items():
                from genweb6.upc.controlpanels.bus_soa import IBusSOASettings
                bussoasettings = registry.forInterface(IBusSOASettings)
                setattr(bussoasettings, key, value)
                logger.info(f"Imported record {key}: {value} to controlpanel: genweb6.upc.controlpanels.bus_soa.IBusSOASettings")

        if "genweb6.upc.controlpanels.identitat_digital.IIdentitatDigitalSettings" in data["controlpanel"]:
            for key, value in data["controlpanel"]["genweb6.upc.controlpanels.identitat_digital.IIdentitatDigitalSettings"].items():
                from genweb6.upc.controlpanels.identitat_digital import IIdentitatDigitalSettings
                identitaldigitalsettings = registry.forInterface(IIdentitatDigitalSettings)
                setattr(identitaldigitalsettings, key, value)
                logger.info(f"Imported record {key}: {value} to controlpanel: genweb6.upc.controlpanels.identitat_digital.IIdentitatDigitalSettings")

        if "genweb6.serveistic.controlpanels.serveistic.IServeisTICControlPanelSettings" in data["controlpanel"]:
            for key, value in data["controlpanel"]["genweb6.serveistic.controlpanels.serveistic.IServeisTICControlPanelSettings"].items():
                from genweb6.serveistic.controlpanels.serveistic import IServeisTICControlPanelSettings
                serveisticsettings = registry.forInterface(IServeisTICControlPanelSettings)
                setattr(serveisticsettings, key, value)
                logger.info(f"Imported record {key}: {value} to controlpanel: genweb6.serveistic.controlpanels.serveistic.IServeisTICControlPanelSettings")

        if "genweb6.serveistic.controlpanels.facetes.IServeisTICFacetesControlPanelSettings" in data["controlpanel"]:
            for key, value in data["controlpanel"]["genweb6.serveistic.controlpanels.facetes.IServeisTICFacetesControlPanelSettings"].items():
                from genweb6.serveistic.controlpanels.facetes import IServeisTICFacetesControlPanelSettings
                serveisticfacetessettings = registry.forInterface(IServeisTICFacetesControlPanelSettings)
                setattr(serveisticfacetessettings, key, value)
                logger.info(f"Imported record {key}: {value} to controlpanel: genweb6.serveistic.controlpanels.facetes.IServeisTICFacetesControlPanelSettings")