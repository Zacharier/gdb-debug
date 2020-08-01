import gdb


class ViewError(IOError): pass

class ArgError(ViewError): pass

class SymbolError(ViewError): pass

class OutBoundError(ViewError): pass

class UnimplementedError(ViewError): pass

class NotFoundError(ViewError): pass


class View(object):
    def __init__(self, name=None):
        self.name = name

    def at(self, val, idx):
        raise UnimplementedError('/i')

    def size(self, val):
        raise UnimplementedError('/l')

    def find(self, val, key):
        raise UnimplementedError('/f')

    def to_string(self, val):
        return str(val)


class ContiguousIterator(object):
    def __init__(self, first, finish):
        self.first = first
        self.finish = finish

    def __iter__(self):
        return self

    def __next__(self):
        if self.first == self.finish:
            raise StopIteration
        retval = self.first.dereference()
        self.first += 1
        return retval;


class StdStringView(View):

    def __init__(self, name=None):
        super().__init__(name or 'std::string')

    def at(self, val, i):
        i = int(i)
        ptr = val['_M_dataplus']['_M_p']
        if i >= self.size(val):
            raise OutBoundError(i)
        return (ptr + i).dereference()

    def size(self, val):
        ptr = val['_M_dataplus']['_M_p']
        head = ptr.cast(gdb.lookup_type('size_t').pointer()) - 3;
        # capacity = (head + 1).dereference()
        # refcount = (head + 2).dereference()
        # return ptr, size, capacity, refcount
        size = head.dereference()
        return int(size)

    def to_string(self, val):
        ptr = val['_M_dataplus']['_M_p']
        iterator = ContiguousIterator(ptr, ptr + self.size(val))
        void_ptr = ptr.cast(gdb.lookup_type('void').pointer())
        return '<address: %s, content: {%s}>' % (void_ptr, bytes(iterator))


class StdCxx11StringView(StdStringView):
    def __init__(self):
        super().__init__('std::__cxx11::string')

    def size(self, val):
        return int(val['_M_string_length'])


class StdVectorView(View):
    def __init__(self):
        super().__init__('std::vector')

    def at(self, val, i):
        i = int(i)
        ptr = val['_M_impl']['_M_start']
        if i >= self.size(val):
            raise OutBoundError(i)
        return (ptr + i).dereference()

    def size(self, val):
        start = val['_M_impl']['_M_start']
        finish = val['_M_impl']['_M_finish']
        return int(finish - start)

    def to_string(self, val):
        start = val['_M_impl']['_M_start']
        finish = val['_M_impl']['_M_finish']
        iterator = ContiguousIterator(start, finish)
        content = ', '.join(map(str, iterator))
        return '<address: %s, content: {%s}>' % (start, content)


class StdUnorderedMapView(View):
    class Iterator(object):
        def __init__(self, val):
            self.node = val['_M_before_begin']['_M_nxt']
            tname = '%s::%s' % (val.type.strip_typedefs(), '__node_type')
            self.type = gdb.lookup_type(tname).pointer()

        def __iter__(self):
            return self

        def __next__(self):
            if self.node == 0:
                raise StopIteration
            entry = self.node.cast(self.type).dereference()
            self.node = entry['_M_nxt']
            ptr = entry['_M_storage'].address
            ptr = ptr.cast(entry.type.template_argument(0).pointer())
            return ptr.dereference()

    def __init__(self):
        super().__init__('std::unordered_map')

    def items(self, val):
        for pair in self.Iterator(val['_M_h']):
            yield pair['first'], pair['second']

    def find(self, val, key):
        equals = lambda x, y: str(x) == '"%s"' % y
        typo = val.type.template_argument(0)
        if typo.code == gdb.TYPE_CODE_INT:
            equals = lambda x, y: int(x) == int(y)

        for first, second in self.items(val):
            if equals(first, key):
                return second
        raise NotFoundError(key)

    def size(self, val):
        return int(val['_M_h']['_M_element_count'])

    def to_string(self, val):
        s = ', '.join(['%s: %s' % pair for pair in self.items(val)])
        return '{%s}' % s


class Viewer(gdb.Command):
    """\
    Usage: v [OPTION]... OBJECT...
    Options:
            /l    get the length or size of object.
            /i    return the item at index of string/vector.
            /f    find the corresponding value by KEY.
    """
    def __init__(self):
        super().__init__("v", gdb.COMMAND_USER)
        pred = lambda vt: isinstance(vt, type) and issubclass(vt, View)
        views = [vt() for vt in globals().values() if pred(vt)]
        self.registry = {view.name : view for view in views}

    def parse(self, args):
        argv = gdb.string_to_argv(args)
        argc = len(argv)
        if argc == 0:
            raise ArgError(args)
        if argc == 1:
            return None, argv[0], ()
        restricts = {
            '/l': 2,
            '/i': 3,
            '/f': 3
        }
        num = restricts.get(argv[0])
        if num and argc == num:
            return argv[0], argv[1], argv[2:]
        raise ArgError(args)

    def view(self, args):
        mode, name, argv = self.parse(args)
        sym, _ = gdb.lookup_symbol(name)
        if not sym:
            raise SymbolError(name)
        value = sym.value(gdb.selected_frame())
        type_name = sym.type.name
        idx = type_name.find('<')
        if idx != -1:
            type_name = type_name[:idx]
        view = self.registry.get(type_name, View)
        mapping = {
            '/l': view.size,
            '/i': view.at,
            '/f': view.find
        }
        method = mapping.get(mode, view.to_string)
        return method(value, *argv)

    def invoke(self, args, from_tty):
        try:
            print(self.view(args))
        except ArgError as e:
            print("Args Error: %s" % e)
        except SymbolError as e:
            print("Symbol Error: %s" % e)
        except OutBoundError as e:
            print("Out Bound Error: %s" % e)
        except UnimplementedError as e:
            print("Unimpelemeted Error: %s'" % e)
        except NotFoundError as e:
            print("Not Found Error: %s" % e)
        except ViewError as e:
            print("Uncaught Error: %s" % e)


Viewer()
