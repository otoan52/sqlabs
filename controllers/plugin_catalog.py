# -*- coding: utf-8 -*-
from plugin_catalog import Catalog
from gluon.tools import Auth
import unittest
from gluon.contrib.populate import populate
from plugin_solidtable import SOLIDTABLE
from plugin_multiselect_widget import hmultiselect_widget
from plugin_tight_input_widget import tight_input_widget
from gluon.validators import Validator
from collections import defaultdict
from gluon.utils import web2py_uuid

if request.function == 'test':
    db = DAL('sqlite:memory:')
    
### setup core objects #########################################################
auth = Auth(db)
catalog = Catalog(db)
catalog.settings.table_product_name = 'plugin_catalog_product'
catalog.settings.table_variant_name = 'plugin_catalog_variant'
catalog.settings.table_option_group_name = 'plugin_catalog_option_group'
catalog.settings.table_option_name = 'plugin_catalog_option'
catalog.settings.extra_fields = {
    'plugin_catalog_product': [
        Field('description', 'text', label=T('Description')),
        Field('image', 'upload', label=T('Image'), autodelete=True, 
              uploadfolder=os.path.join(request.folder, 'uploads'),
              requires=IS_NULL_OR(IS_LENGTH(10240)), comment='size < 10k'),
        Field('created_on', 'datetime', default=request.now, label=T('Created on'),
              readable=False, writable=False),
        # --- Other possible fields ---
        # Field('status'),
        # Field('short_description', 'text'),
        # Field('long_description', 'text'),
        # Field('small_image', 'upload'),
        # Field('large_image', 'upload'),
        # Field('manufacturer'),
        # Field('brand'),
        # Field('reward_point_rate'),
        # Field('keywords'),
    ],
    'plugin_catalog_variant': [
        Field('sale_price', 'integer', label=T('Sale price'), default=0,
              requires=IS_INT_IN_RANGE(0, 1000000),
              widget=tight_input_widget),
        Field('inventory_quantity', 'integer', label=T('Inventory quantity'), default=0,
              requires=IS_INT_IN_RANGE(0, 1000000),
              widget=tight_input_widget),
        # --- Other possible fields ---
        # Field('retail_price', 'integer'),
        # Field('inventory_level', 'integer'),
        # Field('weight', 'integer'),
        # Field('taxable', 'boolean'),
    ],
    # 'plugin_catalog_option': [
        # Field('price_charge'),],
}

### define tables ##############################################################
catalog.define_tables()
table_product = catalog.settings.table_product
table_variant = catalog.settings.table_variant
table_option_group = catalog.settings.table_option_group
table_option = catalog.settings.table_option

### populate records ###########################################################
import datetime
if db(table_product.created_on<request.now-datetime.timedelta(minutes=60)).count():
    for table in (table_product, table_variant, table_option_group, table_option):
        table.truncate()
    session.flash = 'the database has been refreshed'
    redirect(URL('index'))
    
if not db(table_option_group.id>0).count():
    data = {'color': ('red', 'green', 'blue'),
            'size': ('small', 'large'),
            'value': ('1', '2', '3', '4')}
    for option_group_name in data.keys():
        id = table_option_group.insert(name=option_group_name)
        for option_name in data[option_group_name]:
            table_option.insert(option_group=id, name=option_name)

### demo functions #############################################################

# --- common functions ---------------------------------------------------------

MAX_OPTIONS = 2
def option_groups_widget(field, value, **attributes):
    inner = hmultiselect_widget(field, value, **attributes)
    script = SCRIPT(""" 
jQuery(document).ready(function() {
    var buttons = jQuery('#%(id)s input[type=button]');
    buttons.click(function(e){
        var options = jQuery(%(select_el_id)s).children();
        if (options.length > %(max_options)s) {
            alert('! Number of options should be less than or equal to ' + %(max_options)s);
        } else if (options.length == %(max_options)s) {
            jQuery(%(unselected_el_id)s).prop('disabled', true);
            jQuery(buttons[0]).prop('disabled', true);
        } else {
            jQuery(%(unselected_el_id)s).prop('disabled', false);
            jQuery(buttons[0]).prop('disabled', false);
        }
        if (options.length <= %(max_options)s) {
            jQuery('body').trigger('option_groups_changed', 
                jQuery.map(options, function(val){return val.value}).join(','));
        }
    })
}); """ % dict(id=inner.attributes['_id'],
               select_el_id=field.name,
               unselected_el_id="unselected_%s" % field.name,
               max_options=MAX_OPTIONS))
    return SPAN(script, inner)
    
class IS_DELETE_OR(Validator):
    def __init__(self, deleted, other):
        self.deleted, self.other = deleted, other
        
    def __call__(self, value):
        if self.deleted:
            return (value, None)
        if isinstance(self.other, (list, tuple)):
            for item in self.other:
                value, error = item(value)
                if error: break
            return value, error
        else:
            return self.other(value)
           
def variants_widget(field, value, **attributes):
    _id = '%s_%s' % (field._tablename, field.name)
    attr = dict(_type = 'hidden', value = (value!=None and str(value)) or '',
                _id = _id, _name = field.name, requires = field.requires,
                _class = 'string')
    keyword = '_variants'
    disp_el_id='_variants_disp_el_id'
    ajax = (keyword in request.vars)
    
    trigger = request.vars.option_groups
    if type(trigger) == list:
        trigger = ','.join(trigger)
        
    option_group_ids = [option_group_id for option_group_id 
                            in (request.vars.get(keyword, '') or trigger or '').split(',')
                                if option_group_id]
    
    def _get_variant_elements(option_set_key, sort_order=0):
        def _get_field_comment(name):
            if option_set_key != 'master':
                return INPUT(_type='button', _value=T('Apply all'),
                             _onclick='apply_for_all_variants("%s", "%s");' % (option_set_key, name))
        
        deleted = (option_set_key != 'master') and not request.vars.get('variant__%s__available' % option_set_key)
        fields = []
        hidden = {}
        for f in table_variant:
            new_name = 'variant__%s__%s' % (option_set_key, f.name)
            
            if f.name == 'sort_order':
                f.default = sort_order
                
            if ajax:
                default = f.default
            else:
                default = request.vars.get('variant__%s__%s' % (option_set_key, f.name)) or f.default

            if f.name == 'sort_order':
                hidden[new_name] = f.default
                continue
            elif f.name == 'sku':
                default = default or web2py_uuid()
                
            fields.append(Field(new_name, f.type, 
                        readable=f.readable, writable=f.writable, label=f.label, 
                        requires=IS_DELETE_OR(deleted, f.requires), widget=f.widget,
                        default=default, comment=_get_field_comment(f.name)))
        
        if option_set_key != 'master':
            fields.insert(0, Field('variant__%s__available' % option_set_key, 
                                   'boolean', default=True if ajax else not deleted, 
                                    label=T('Available'), comment=_get_field_comment('available')))
                                    
        form = SQLFORM.factory(buttons=[], hidden=hidden, *fields)
        
        trs = form.elements('tr')
        fls = []
        fws = []
        fcs = []
        for tr in trs:
            fl, fw, fc = tr.elements('td')
            fls.append(fl)
            fws.append(fw)
            fcs.append(fc)
            
        return fls, fws, fcs, form.hidden_fields()
        
    def _render_variants():
        option_sets = catalog.get_option_sets(option_group_ids)
        if not option_sets:
            fls, fws, fcs, hidden = _get_variant_elements('master')
            return TABLE([TR(fls[i], fws[i], fcs[i]) for i in range(len(fls))], hidden)
        
        option_set_keys = ['_'.join([str(option.id) for option in option_set])
                                for option_set in option_sets]
        
        script = SCRIPT(""" 
jQuery.fn.mod_val = function(value){
    var el = jQuery(this);
    if (value === undefined) {
        if(el.is("input[type=checkbox]")) { return el.is(":checked");}
        else { return el.val(); }
    } else {
        if(el.is("input[type=checkbox]")) { return el.prop('checked', value); }
        else { return el.val(value); }
    }
};
function apply_for_all_variants(option_set_key, name) { 
    var option_set_keys = %s;
    var value = jQuery("[name=variant__"+option_set_key+"__"+name+"]").mod_val();
    jQuery.each(option_set_keys, function() {
        jQuery("[name=variant__"+this+"__"+name+"]").mod_val(value);
    });
}""" % ('["%s"]' % '","'.join(option_set_keys)))
   
        table_inner = []
        for sort_order, (option_set_key, option_set) in enumerate(zip(option_set_keys, option_sets)):
            fls, fws, fcs, hidden = _get_variant_elements(option_set_key, sort_order)
            if sort_order == 0:
                table_inner.append(TR(TD(LABEL(T('Option groups'), hidden), script), *fls))
            tr_inner = [TD(H4(':'.join([r.name for r in option_set])))]
            if sort_order == 0:
                tr_inner.extend([TD(SPAN(*fws[i].components), 
                                    SPAN(*fcs[i].components)) for i in range(len(fls))])
            else:
                tr_inner.extend([TD(SPAN(*fws[i].components)) for i in range(len(fls))])
            table_inner. append(TR(*tr_inner))
        return TABLE(*table_inner) 
        
    if ajax:
        raise HTTP(200, _render_variants())
         
    script = SCRIPT(""" 
jQuery(document).ready(function() {
    jQuery('body').bind('option_groups_changed', function(e, val) {
        var query = {}
        query["%(keyword)s"] = val;
        jQuery.ajax({type: "POST", url: "%(url)s", data: query, 
            success: function(html) {
              jQuery("#%(disp_el_id)s").html(html);
        }});
    });
}); """ % dict(keyword=keyword, 
               url=URL(r=request, args=request.args), 
               disp_el_id=disp_el_id))
               
    return SPAN(script, INPUT(**attr), DIV(_render_variants(), _id=disp_el_id), **attributes)
    
def get_variant_vars_list(vars):
    reduced_vars_dict = defaultdict(dict)
    for k, v in vars.items():
        if k.startswith('variant__'):
            option_set_key, var_name = k.split('__')[1:3]
            reduced_vars_dict[option_set_key][var_name] = v
    variant_vars_list = []        
    for option_set_key, reduced_vars in reduced_vars_dict.items():
        if option_set_key == 'master':
            reduced_vars['options'] = []
            variant_vars_list.append(reduced_vars)
        elif reduced_vars.get('available'):
            reduced_vars['options'] = option_set_key.split('_')
            variant_vars_list.append(reduced_vars)  
    return variant_vars_list
    
def process_variants_requires():
    variants_requires = None
    if request.vars.option_groups:
        if all(not v for k, v in request.vars.items() 
                     if k.startswith('variant__') and k.endswith('__available')):
            variants_requires = IS_NOT_EMPTY('Input at least one variant')
    return variants_requires

# --- expose funcitons ---------------------------------------------------------

def index():
    if not request.args(0):
        form = SQLFORM.factory(table_product, 
                               Field('option_groups', 'list:reference', 
                                     label=T('Option groups'),
                                     widget=option_groups_widget,
                                     requires=IS_EMPTY_OR(IS_IN_DB(db, 
                                                table_option_group.id, '%(name)s', multiple=True))),
                               Field('variants', widget=variants_widget,
                                     label=T('Variants'),
                                     requires=process_variants_requires()),
                               table_name=str(table_product),
                               formstyle = 'ul',
                               )
        
        form.validate()  
        if form.accepted:
            catalog.add_product(form.vars, get_variant_vars_list(form.vars))
            session.flash = T('Record Created')
            redirect(URL())
        
        extracolumns = [{'label':T('Sale price'),
                         'content':lambda row, rc: '%s - %s' % (
                                                    row.variants and min([v.sale_price for v in row.variants]),
                                                    row.variants and max([v.sale_price for v in row.variants]))
                                                    if row.option_groups else row.variants[0].sale_price},
                        {'label':T('Option groups'),
                         'content':lambda row, rc: ', '.join([og.name for og in row.option_groups]) or '*master*'},
                        {'label':T('Options'),
                         'content':lambda row, rc: ', '.join([':'.join([o.name for o in v.options]) 
                                                                            for v in row.variants]) or '*master*'},
                        {'label':T('View'),
                         'content':lambda row, rc: A('View', _href=URL('index', args=['view', row.id]))},   
                        {'label':T('Edit'),
                         'content':lambda row, rc: A('Edit', _href=URL('index', args=['edit', row.id]))},
                        {'label':T('Delete'),
                         'content':lambda row, rc: A('Delete', _href=URL('index', args=['delete', row.id]))},
                    ]
        
        products = catalog.get_products_by_query(table_product.id>0, orderby=~table_product.id)
        products = SOLIDTABLE(products, 
                              headers='labels', extracolumns=extracolumns)
        return dict(product_form=form, 
                    products=products,
                    unit_tests=[A('basic test', _href=URL('test'))])
    
    elif request.args(0) == 'edit':
        product_id = request.args(1)
        product = catalog.get_product(product_id, load_option_groups=False)
        if not product:
            session.flash = 'the database has been refreshed'
            redirect(URL())
            
        request.vars.option_groups = request.vars.option_groups or map(str, product.option_groups)
        variants_requires = process_variants_requires()
           
        for variant in product.variants:
            if not product.option_groups:
                option_set_key = 'master'
            else:
                option_set_key = '_'.join([str(option.id) for option in variant.options])
                request.vars['variant__%s__available' % option_set_key] = True
            for name in variant:
                request.vars['variant__%s__%s' % (option_set_key, name)] = variant[name]
        
        form = SQLFORM(DAL(None).define_table(str(table_product),
                               table_product, 
                               Field('option_groups', 'list:reference', 
                                     label=T('Option groups'),
                                     widget=option_groups_widget,
                                     default=product.option_groups or None,
                                     requires=IS_EMPTY_OR(IS_IN_DB(db, 
                                                table_option_group.id, '%(name)s', multiple=True))),
                               Field('variants', widget=variants_widget,
                                     label=T('Variants'),
                                     requires=variants_requires)), 
                               product,
                               upload=URL('download'),
                               formstyle='ul')
                               
        form.validate()  
        if form.accepted:
            catalog.edit_product(product_id, form.vars, get_variant_vars_list(form.vars))
            session.flash = T('Record Updated')
            redirect(URL())
        
        return dict(back=A('back', _href=URL('index')), product_form=form)
                    
    elif request.args(0) == 'view':
        product_id = request.args(1)
        product = catalog.get_product(product_id)
        form = SQLFORM(table_product, product, readonly=True,
                       upload=URL('download'))
        
        option_groups = [r.name for r in product.option_groups]
        
        variants = ['-'.join([o.name for o in variant.options]) or '*master*' + 
                    ' : ' + variant.sku  
                        for variant in product.variants]
        
        return dict(back=A('back', _href=URL('index')), 
                    product=form,
                    product_option_groups=option_groups,
                    variants=variants)
        
    elif request.args(0) == 'delete':
        product_id = request.args(1)
        catalog.remove_product(product_id)
        session.flash = T('Record Deleted')
        redirect(URL())
        
def download():
    return response.download(request, db)
  
### unit tests #################################################################
class TestCatalog(unittest.TestCase):

    def setUp(self):
        table_product.truncate()
        
    def test_basic(self):
        pass
        
def run_test(TestCase):
    import cStringIO
    stream = cStringIO.StringIO()
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCase)
    unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return stream.getvalue()
    
def test():
    return dict(back=A('back', _href=URL('index')),
                output=CODE(run_test(TestCatalog)))
        