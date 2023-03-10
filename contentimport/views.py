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

IMAGE_MODIFY = {
    "/example-owl.jpeg": "++theme++genweb6.theme/img/sample/owl.jpeg",
    "/example-fox.jpeg": "++theme++genweb6.theme/img/sample/fox.jpeg",
    "/example-penguin.jpeg": "++theme++genweb6.theme/img/sample/penguin.jpeg",
    "/example-artic-fox.jpeg": "++theme++genweb6.theme/img/sample/artic-fox.jpeg",
    "/banerMostra1linia_gw3.png": "++theme++genweb6.theme/img/sample/owl.jpeg",
    "/car1.jpg": "++theme++genweb6.theme/img/sample/wolf.jpeg",
    "/car2.jpg": "++theme++genweb6.theme/img/sample/turtle.jpeg",
    "/mostra.jpg": "++theme++genweb6.theme/img/sample/wolf.jpeg",
    "/sampleimg1.jpg": "++theme++genweb6.theme/img/sample/wolf.jpeg",
    "/sampleimg2.jpg": "++theme++genweb6.theme/img/sample/wolf.jpeg",
    "/sampleimg3.jpg": "++theme++genweb6.theme/img/sample/wolf.jpeg",
    "/sampleimg4.jpg": "++theme++genweb6.theme/img/sample/wolf.jpeg",
    "/sampleimg5.jpg": "++theme++genweb6.theme/img/sample/wolf.jpeg",
    "/sampleimg6.jpg": "++theme++genweb6.theme/img/sample/wolf.jpeg",
    "/sampleimg7.jpg": "++theme++genweb6.theme/img/sample/wolf.jpeg",
    "/sampleimg8.jpg": "++theme++genweb6.theme/img/sample/wolf.jpeg",
    "/sampleimg9.jpg": "++theme++genweb6.theme/img/sample/wolf.jpeg",
    "/sampleimg10.jpg": "++theme++genweb6.theme/img/sample/wolf.jpeg",
    "/sampleimg11.jpg": "++theme++genweb6.theme/img/sample/wolf.jpeg",
    "/anecs-petit.jpeg": "++theme++genweb6.theme/img/sample/fox.jpeg",
    "/anecs-gran.jpg": "++theme++genweb6.theme/img/sample/fox.jpeg",
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

        fixers = [fix_modify_image_gw4, fix_img_icon_blanc, fix_nav_tabs_box, fix_nav_tabs, fix_accordion, fix_carousel, fix_modify_class]
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

def fix_img_icon_blanc(text, obj=None):
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

def fix_nav_tabs(text, obj=None):
    """Modificar bootstrap antiguo pesta??as"""
    if not text:
        return text

    if isinstance(text, str):
        soup = BeautifulSoup(text, "html.parser")
        istext = True
    else:
        soup = text
        istext = False

    for ul_nav_tabs in soup.find_all("ul", class_="nav nav-tabs"):
        classes = ul_nav_tabs.get("class", [])
        classes.append("nav-gw4")
        classes.append("mb-3")
        ul_nav_tabs.attrs.update({"role":"tablist"})
        for li in ul_nav_tabs.find_all("li"):
            classes = li.get("class", [])
            href = li.a.get("href")
            if '#' in href:
                href_sin = href[1:]
            if "active" in classes:
                new_li = str('<li class="nav-item" role="presentation"><button id="' + href_sin + '-tab" class="nav-link active" data-bs-toggle="tab" data-bs-target= ' +  href + ' type="button" aria-selected="true" role="tab" aria-controls=' + href_sin + '>' + li.a.get_text() + '</button></li>')
                soup_li =  BeautifulSoup(new_li, "html.parser")
                new_tag_li = soup_li.find_all("li")
                li.replace_with(new_tag_li[0])
            else:
                new_li = str('<li class="nav-item" role="presentation"><button id="' + href_sin + '-tab" class="nav-link" data-bs-toggle="tab" data-bs-target= ' +  href + ' type="button" aria-selected="false" role="tab" aria-controls=' + href_sin + '>' + li.a.get_text() + '</button></li>')
                soup_li =  BeautifulSoup(new_li, "html.parser")
                new_tag_li = soup_li.find_all("li")
                li.replace_with(new_tag_li[0])
        msg = "Fixed html nav_tabs {}".format(obj.absolute_url())
        logger.info(msg)
    for div in soup.find_all("div", class_="tab-content"):
        for tag in div.find_all("div", class_="tab-pane"):
            classes = tag.get("class", [])
            classes.append("fade")
            tag.attrs.update({"role":"tabpanel"})
            tag.attrs.update({"aria-labelledby": tag.get("id", []) + "-tab"})
            tag.attrs.update({"tabindex":"0"})
            if "active" in classes:
                classes.append("show")

    if istext:
        return soup.decode()
    else:
        return soup

def fix_nav_tabs_box(text, obj=None):
    """Modify tabs_box old to new bootstrap"""
    if not text:
        return text

    if isinstance(text, str):
        soup = BeautifulSoup(text, "html.parser")
        istext = True
    else:
        soup = text
        istext = False

    for div_beautytab in soup.find_all("div", class_="beautytab"):
        classes = div_beautytab.get("class", [])
        classes.append("card")
        classes.append("nav-box-gw4")
        classes.append("mb-3")
        classes.remove("beautytab")
        for tag in div_beautytab.find_all("ul"):
            classes = tag.get("class", [])
            if classes:
                classes.append("nav")
                classes.append("nav-tabs")
                classes.append("nav-card-gw4")
                classes.append("px-1")
                classes.append("pt-1")
            else:
                tag.attrs.update({"class":"nav nav-tabs nav-card-gw4 px-1 pt-1"})
            tag.attrs.update({"role":"tablist"})
            for li in tag.find_all("li"):
                classes = li.get("class", [])
                href = li.a.get("href")
                if '#' in href:
                    href_sin = href[1:]
                if "active" in classes:
                    new_li = str('<li class="nav-item" role="presentation"><button id="' + href_sin + '-tab" class="nav-link active" data-bs-toggle="tab" data-bs-target= ' +  href + ' type="button" aria-selected="true" role="tab" aria-controls=' + href_sin + '>' + li.a.get_text() + '</button></li>')
                    soup_li =  BeautifulSoup(new_li, "html.parser")
                    new_tag_li = soup_li.find_all("li")
                    li.replace_with(new_tag_li[0])
                else:
                    new_li = str('<li class="nav-item" role="presentation"><button id="' + href_sin + '-tab" class="nav-link" data-bs-toggle="tab" data-bs-target= ' +  href + ' type="button" aria-selected="false" role="tab" aria-controls=' + href_sin + '>' + li.a.get_text() + '</button></li>')
                    soup_li =  BeautifulSoup(new_li, "html.parser")
                    new_tag_li = soup_li.find_all("li")
                    li.replace_with(new_tag_li[0])
        for div_content in div_beautytab.find_all("div", class_="tab-content"):
            classes = div_content.get("class", [])
            classes.remove("beautytab-content")
            for div_tab_pane in div_content.find_all("div", class_="tab-pane"):
                classes = div_tab_pane.get("class", [])
                classes.append("fade")
                div_tab_pane.attrs.update({"role":"tabpanel"})
                div_tab_pane.attrs.update({"aria-labelledby": tag.get("id", []) + "-tab"})
                div_tab_pane.attrs.update({"tabindex":"0"})
                if "active" in classes:
                    classes.append("show")
        msg = "Fixed html fix_nav_tabs_box {}".format(obj.absolute_url())
        logger.info(msg)

    if istext:
        return soup.decode()
    else:
        return soup

def fix_accordion(text, obj=None):
    """Modify accordion old to new bootstrap"""
    if not text:
        return text

    if isinstance(text, str):
        soup = BeautifulSoup(text, "html.parser")
        istext = True
    else:
        soup = text
        istext = False

    for div_accordion in soup.find_all("div", class_="accordion"):
        classes = div_accordion.get("class", [])
        classes.append("accordion-gw4")
        classes.append("mb-3")
        for div_accordion_item in div_accordion.find_all("div", class_="accordion-group"):
            classes = div_accordion_item.get("class", [])
            classes.append("accordion-item")
            classes.remove("accordion-group")
            for div_head in div_accordion_item.find_all("div", class_="accordion-heading"):
                href = div_head.a.get("href")
                if '#' in href:
                    href_sin = href[1:]
                data_parent = div_head.a.get("data-parent")
                new_h2 = str('<h2 class="accordion-header" id="' + href_sin + 'Heading"><button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="' + href + '" aria-expanded="false" aria-controls="' + href + '">' + div_head.a.get_text() + '</button></h2>')
                soup_h2 =  BeautifulSoup(new_h2, "html.parser")
                new_tag_h2 = soup_h2.find_all("h2")
                div_head.replace_with(new_tag_h2[0])
            for div_body in div_accordion_item.find_all("div", class_="accordion-body"):
                classes = div_body.get("class", [])
                classes.append("accordion-collapse")
                classes.remove("accordion-body")
                div_body.attrs.update({"aria-labelledby": href_sin + "Heading"})
                div_body.attrs.update({"data-bs-parent": data_parent})
            for div_inner in div_accordion_item.find_all("div", class_="accordion-inner"):
                classes = div_inner.get("class", [])
                classes.append("accordion-body")
                classes.remove("accordion-inner")
        msg = "Fixed html fix_accordion {}".format(obj.absolute_url())
        logger.info(msg)

    if istext:
        return soup.decode()
    else:
        return soup

def fix_carousel(text, obj=None):
    """Modify carousel old to new bootstrap"""
    if not text:
        return text

    if isinstance(text, str):
        soup_ini = BeautifulSoup(text, "html.parser")
        istext = True
    else:
        soup_ini = text
        text = text.prettify()
        istext = False

    for div_carousel in soup_ini.find_all("div", class_="carousel"):
        new_text = str('<div class="template-carousel">' + text + '</div>')
        soup = BeautifulSoup(new_text, "html.parser")
        for div_carousel in soup.find_all("div", class_="carousel"):
            classes = div_carousel.get("class", [])
            classes.append("carousel-dark")
            classes.append("mb-2")
            classes.append("carousel-gw4")
            for div_carousel_inner in div_carousel.find_all("div", class_="carousel-inner"):
                for div_carousel_item in div_carousel_inner.find_all("div", class_="item"):
                    classes = div_carousel_item.get("class", [])
                    classes.append("carousel-item")
                    classes.remove("item")
                    div_carousel_item.attrs.update({"data-bs-interval": 10000})
                    for image in div_carousel_item.find_all("img"):
                        classes = image.get("class", [])
                        classes.append("d-block")
                        classes.append("w-100")
                    for div_carousel_caption in div_carousel_item.find_all("div", class_="carousel-caption"):
                        classesh4 = div_carousel_caption.h4.get("class", [])
                        classesh4.append("text-truncate")
                        try:
                            classesp = div_carousel_caption.p.get("class", [])
                            classesp.append("text-truncate-2")
                            classesp.append("mb-1")
                        except:
                            continue
            for a_carousel_control in div_carousel.find_all("a", class_="carousel-control"):
                href = a_carousel_control.get("href")
                if '#' in href:
                    href_sin = href[1:]
                if "prev" in a_carousel_control.get("data-slide"):
                    new_button_prev = str('<button class="carousel-control-prev" type="button" data-bs-slide="prev" data-bs-target="' + href + '"><span class="carousel-control-prev-icon" aria-hidden="true"></span><span class="visually-hidden">Previous</span></button>')
                    soup_button_prev =  BeautifulSoup(new_button_prev, "html.parser")
                    new_tag_button_prev = soup_button_prev.find_all("button")
                    a_carousel_control.replace_with(new_tag_button_prev[0])

                if "next" in a_carousel_control.get("data-slide"):
                    new_button_next = str('<button class="carousel-control-next" type="button" data-bs-slide="next" data-bs-target="' + href + '"><span class="carousel-control-next-icon" aria-hidden="true"></span><span class="visually-hidden">Next</span></button>')
                    soup_button_next =  BeautifulSoup(new_button_next, "html.parser")
                    new_tag_button_next = soup_button_next.find_all("button")
                    a_carousel_control.replace_with(new_tag_button_next[0])

            msg = "Fixed html fix_carousel {}".format(obj.absolute_url())
            logger.info(msg)

        if istext:
            return soup.decode()
        else:
            return soup

def fix_modify_class(text, obj=None):
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

def fix_modify_image_gw4(text, obj=None):
    """Modify image genweb 4"""
    if not text:
        return text

    soup = BeautifulSoup(text, "html.parser")
    for image in soup.find_all("img"):
        for olds, news in IMAGE_MODIFY.items():
            if olds in image["src"]:
                image.attrs.update({"src": news})
                try:
                    if olds in image.parent.attrs["href"]:
                        image.parent.attrs.update({"href": obj.portal_url() + '/' + news})
                except:
                    continue
                try:
                    if olds in image.parent.parent.attrs["href"]:
                        image.parent.parent.attrs.update({"href": obj.portal_url() + '/' + news})
                except:
                    continue
                msg = "Fixed html image {} in object {}".format(news, obj.absolute_url())
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

    if soup.find_all("div", {"class": "beautytab"}):
        soup = fix_nav_tabs_box(soup, obj)

    if soup.find_all("ul", {"class": "nav nav-tabs"}):
        soup = fix_nav_tabs(soup, obj)

    if soup.find_all("div", {"class": "accordion"}):
        soup = fix_accordion(soup, obj)

    if soup.find_all("div", {"class": "carousel"}):
        soup = fix_carousel(soup, obj)

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
