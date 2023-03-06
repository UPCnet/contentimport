from App.config import getConfiguration
from bs4 import BeautifulSoup
from collective.exportimport.fix_html import fix_html_in_content_fields
from collective.exportimport.fix_html import fix_html_in_portlets
from collective.exportimport.fix_html import fix_tag_attr
from contentimport.interfaces import IContentimportLayer
from logging import getLogger
from pathlib import Path
from plone import api
from Products.CMFPlone.utils import get_installer
from Products.Five import BrowserView
from plone.app.portlets.interfaces import IPortletTypeInterface
from plone.app.textfield import RichTextValue
from plone.app.textfield.interfaces import IRichText
from plone.app.textfield.value import IRichTextValue
from plone.portlets.interfaces import IPortletAssignmentMapping
from plone.portlets.interfaces import IPortletManager
from zope.component import getUtilitiesFor
from zope.component import queryMultiAdapter
from zope.interface import alsoProvides
from zope.interface import providedBy

import transaction

logger = getLogger(__name__)

DEFAULT_ADDONS = []

CLASS_MODIFY = {
    "row-fluid": "row",
    "span1": "col-md-1",
    "span2": "col-md-2",
    "span3": "col-md-3",
    "span4": "col-md-4",
    "span5": "col-md-5",
    "span6": "col-md-6",
    "span7": "col-md-7",
    "span8": "col-md-8",
    "span9": "col-md-9",
    "span10": "col-md-10",
    "span11": "col-md-11",
    "span12": "col-md-12",
    "lead": "card p-3 text-bg-light",
    "taulaRegistres": "table table-stripped",
    "xlsdf": "xls",
    "carousel slide": "carousel slide gw4-carousel",
}

class ImportAll(BrowserView):

    def __call__(self):
        request = self.request
        if not request.form.get("form.submitted", False):
            return self.index()

        portal = api.portal.get()
        alsoProvides(request, IContentimportLayer)

        installer = get_installer(portal)
        if not installer.is_product_installed("contentimport"):
            installer.install_product("contentimport")

        # install required addons
        for addon in DEFAULT_ADDONS:
            if not installer.is_product_installed(addon):
                installer.install_product(addon)

        transaction.commit()
        cfg = getConfiguration()
        directory = Path(cfg.clienthome) / "import"

        # import content
        view = api.content.get_view("import_content", portal, request)
        request.form["form.submitted"] = True
        request.form["commit"] = 500
        view(server_file=portal.id + ".json", return_json=True)
        transaction.commit()

        other_imports = [
            "relations",
            "translations",
            "members",
            "localroles",
            "defaultpages",
            "ordering",
            "discussion",
            "portlets",
            "redirects",
            "controlpanels",
        ]

        for name in other_imports:
            view = api.content.get_view(f"import_{name}", portal, request)
            path = Path(directory) / f"export_{name}.json"
            if path.exists():
                results = view(jsonfile=path.read_text(), return_json=True)
                logger.info(results)
                transaction.commit()
            else:
                logger.info(f"Missing file: {path}")

        fixers = [img_icon_blanc, nav_tabs, modify_class]
        results = fix_html_in_content_fields(fixers=fixers)
        msg = "Fixed html for {} content items".format(results)
        logger.info(msg)
        transaction.commit()

        results = fix_html_in_portlets()
        msg = "Fixed html for {} portlets".format(results)
        logger.info(msg)
        transaction.commit()

        # Rebuilding the catalog is necessary to prevent issues later on
        catalog = api.portal.get_tool("portal_catalog")
        logger.info("Rebuilding catalog...")
        catalog.clearFindAndRebuild()
        msg = "Finished rebuilding catalog!"
        logger.info(msg)
        transaction.get().note(msg)
        transaction.commit()

        # No lo utilizo son ejemplos de Philip Bauer
        # reset_dates = api.content.get_view("reset_dates", portal, request)
        # reset_dates()
        # transaction.commit()

        return request.response.redirect(portal.absolute_url())

def img_icon_blanc(text, obj=None):
    """Delete image icon blanc"""
    if not text:
        return text

    soup = BeautifulSoup(text, "html.parser")
    for tag in soup.find_all("img"):
        classes = tag.get("class", [])
        if "link_blank" in classes:
            # delete image
            tag.decompose()
        else:
            continue
    return soup.decode()

def nav_tabs(text, obj=None):
    """Modificar bootstrap antiguo pestañas"""
    if not text:
        return text

    soup = BeautifulSoup(text, "html.parser")
    for tag in soup.find_all("ul", class_="nav nav-tabs"):
        classes = tag.get("class", [])
        classes.append("nav-gw4")
        for li in tag.find_all("li"):
            classes = li.get("class", [])
            if "active" in classes:
                new_li = str('<li class="nav-item"><button class="nav-link active" data-bs-toggle=' + li.a.get("data-toggle") + ' data-bs-target=' +  li.a.get("href") + ' type="button" aria-selected="true">' + li.a.get_text() + '</button></li>')
                soup_li =  BeautifulSoup(new_li, "html.parser")
                new_tag_li = soup_li.find_all("li")
                li.replace_with(new_tag_li[0])
            else:
                new_li = str('<li class="nav-item"><button class="nav-link" data-bs-toggle=' + li.a.get("data-toggle") + ' data-bs-target=' +  li.a.get("href") + ' type="button" aria-selected="false">' + li.a.get_text() + '</button></li>')
                soup_li =  BeautifulSoup(new_li, "html.parser")
                new_tag_li = soup_li.find_all("li")
                li.replace_with(new_tag_li[0])
        msg = "Fixed html nav_tabs {}".format(obj.absolute_url())
        logger.info(msg)
    for tag in soup.find_all("div", class_="tab-pane"):
        classes = tag.get("class", [])
        if "tab-pane" and "active" in classes:
            classes.append("fade")
            classes.append("show")
        else:
            classes.append("fade")
    return soup.decode()

def modify_class(text, obj=None):
    """Modificar classes bootstrap"""
    if not text:
        return text

    soup = BeautifulSoup(text, "html.parser")
    for olds, news in CLASS_MODIFY.items():
        for tag in soup.find_all(class_=olds):
            classes = tag.get("class", [])
            for old in olds.split():
                classes.remove(old)
            for new in news.split():
                classes.append(new)
            msg = "Fixed html class {} in object {}".format(news, obj.absolute_url())
            logger.info(msg)
    return soup.decode()

#No he modificado la funcion pero la necesito para poder modificar el html_fixer
def fix_html_in_portlets(context=None):

    portlets_schemata = {
        iface: name for name, iface in getUtilitiesFor(IPortletTypeInterface)
    }

    def get_portlets(obj, path, fix_count_ref):
        for manager_name, manager in getUtilitiesFor(IPortletManager):
            mapping = queryMultiAdapter((obj, manager), IPortletAssignmentMapping)
            if mapping is None or not mapping.items():
                continue
            mapping = mapping.__of__(obj)
            for name, assignment in mapping.items():
                portlet_type = None
                schema = None
                for schema in providedBy(assignment).flattened():
                    portlet_type = portlets_schemata.get(schema, None)
                    if portlet_type is not None:
                        break
                assignment = assignment.__of__(mapping)
                for fieldname, field in schema.namesAndDescriptions():
                    if IRichText.providedBy(field):
                        text = getattr(assignment, fieldname, None)
                        if text and IRichTextValue.providedBy(text) and text.raw:
                            clean_text = html_fixer(text.raw, obj)
                            if clean_text and clean_text != text.raw:
                                textvalue = RichTextValue(
                                    raw=clean_text,
                                    mimeType=text.mimeType,
                                    outputMimeType=text.outputMimeType,
                                    encoding=text.encoding,
                                )
                                fix_count_ref.append(True)
                                setattr(assignment, fieldname, textvalue)
                                logger.info(
                                    "Fixed html for field {} of portlet at {}".format(
                                        fieldname, obj.absolute_url()
                                    )
                                )
                        elif text and isinstance(text, str):
                            clean_text = html_fixer(text, obj)
                            if clean_text and clean_text != text:
                                textvalue = RichTextValue(
                                    raw=clean_text,
                                    mimeType="text/html",
                                    outputMimeType="text/x-html-safe",
                                    encoding="utf-8",
                                )
                                fix_count_ref.append(True)
                                setattr(assignment, fieldname, textvalue)
                                logger.info(
                                    "Fixed html for field {} of portlet {} at {}".format(
                                        fieldname, str(assignment), obj.absolute_url()
                                    )
                                )

    if context is None:
        context = api.portal.get()
    fix_count = []
    f = lambda obj, path: get_portlets(obj, path, fix_count)
    context.ZopeFindAndApply(context, search_sub=True, apply_func=f)
    return len(fix_count)

def html_fixer(text, obj=None, old_portal_url=None):
    # Fix issues with migrated html
    #
    # 1. Fix image scales from old to new types
    # 2. Add data-attributes to internal links and images fix editing in TinyMCE
    if not text:
        return

    portal = api.portal.get()
    portal_url = portal.absolute_url()
    if old_portal_url is None:
        old_portal_url = portal_url

    soup = BeautifulSoup(text, "html.parser")
    for tag, attr in [
        (tag, attr)
        for attr, tags in [
            ("href", ["a"]),
            ("src", ["source", "img", "video", "audio", "iframe"]),
            ("srcset", ["source", "img"]),
        ]
        for tag in tags
    ]:
        fix_tag_attr(soup, tag, attr, old_portal_url, obj=obj)

    #Migration genweb
    for tag in soup.find_all("img"):
        classes = tag.get("class", [])
        if "link_blank" in classes:
            # delete image
            tag.decompose()
        else:
            continue
    #FI Migration genweb
    return soup.decode()

# def table_class_fixer(text, obj=None):
#     if "table" not in text:
#         return text
#     dropped_classes = [
#         "MsoNormalTable",
#         "MsoTableGrid",
#     ]
#     replaced_classes = {
#         "invisible": "invisible-grid",
#     }
#     soup = BeautifulSoup(text, "html.parser")
#     for table in soup.find_all("table"):
#         table_classes = table.get("class", [])
#         for dropped in dropped_classes:
#             if dropped in table_classes:
#                 table_classes.remove(dropped)
#         for old, new in replaced_classes.items():
#             if old in table_classes:
#                 table_classes.remove(old)
#                 table_classes.append(new)
#         # all tables get the default bootstrap table class
#         if "table" not in table_classes:
#             table_classes.insert(0, "table")

#     return soup.decode()

# def img_variant_fixer(text, obj=None, fallback_variant=None):
#     """Set image-variants"""
#     if not text:
#         return text

#     scale_variant_mapping = _get_picture_variant_mapping()
#     if fallback_variant is None:
#         fallback_variant = FALLBACK_VARIANT

#     soup = BeautifulSoup(text, "html.parser")
#     for tag in soup.find_all("img"):
#         if "data-val" not in tag.attrs:
#             # maybe external image
#             continue
#         scale = tag["data-scale"]
#         variant = scale_variant_mapping.get(scale, fallback_variant)
#         tag["data-picturevariant"] = variant

#         classes = tag["class"]
#         new_class = "picture-variant-{}".format(variant)
#         if new_class not in classes:
#             classes.append(new_class)
#             tag["class"] = classes

#     return soup.decode()
