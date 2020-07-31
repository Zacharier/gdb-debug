# 扩展

gdb支持用户自定义扩展来增强gdb的调试能力。目前支持使用Python或者Guile（Scheme语言的一种实现）来进行扩展。这里单讲如何编写Python扩展部分。

我们将通过一个实际的例子来讲述Python扩展的一些基本概念，并最终通过gdb提供的官方Python API来编写一个实用命令。

## 扩展命令
gdb有一个很强大的`examine`命令——`x`。`x`命令是专门用来查看指针所指一片连续的内存内容的，但无法应用到C++容器中。我们仿照`x`来实现一个新的gdb命令`View`——`v`。该命令通过Python扩展实现主要功能有：

*  获取C++容器的各种内部信息，包括内容、首地址、长度等信息；
*  支持查找、下标访问等行为。

要获取容器信息，必须要了解gcc中各种容器的源码实现。此外，我们通过`x`或者`p`命令也可以获取容器的各种信息，但也是要事先了解容器的源码实现。

## C++容器
这里介绍如下三种常用容器的源码实现：
1. `std::string`
2. `std::vector`
3. `std::unordered_map`

讲解的源码版本为gcc 8.3.0，源码地址：http://mirror.hust.edu.cn/gnu/gcc/gcc-8.3.0/

*gcc在版本4.x以后，容器的内存布局甚至是成员变量名均少有变化，因此该部分介绍的内容可以适用于目前绝大多数的gcc版本。在不同版本或者ABI下有较大差异的实现下文也会单独注明*

### std::string

`std::string`的内部持有一块连续性内存，一般的实现为内部一个成员指针`char*`指向一段动态申请的内存，并同时内部记录当前字符串的长度（length），以及这段内存的大小，通常称为容量（capacity）。如果内存不够则进行扩展（resize/reserve），即申请一段新的内存，将旧内存上的数据拷贝过来，释放旧内存。最终这段动态申请的内存在析构函数中释放。

该版本的实现存在两个版本，通过`_GLIBCXX_USE_CXX11_ABI`宏来区分不同的版本。

在gcc4.x以后string的实现基于引用计数的COW（Copy On Write），内存布局如下：

![string_cow](https://raw.githubusercontent.com/Zacharier/gdb-debug/master/assets/img/string_cow.png)

在gcc7.x以上，默认启用C++11 ABI宏的本地Buff实现，内存布局如下：

![string_buf](https://raw.githubusercontent.com/Zacharier/gdb-debug/master/assets/img/string_buf.png)

### std::vector

`std::vector`的实现和`std::string`基本一致，包括内部动态内存的扩展机制。这里不多介绍，内存布局如下：

![vector](https://raw.githubusercontent.com/Zacharier/gdb-debug/master/assets/img/vector.png)

### std::unordered_map

`std::unordered_map`即哈希表。内部由一个桶数组和链表实现，即经典的链式哈希表。内存布局如下

注意：这个实现版本将有元素的桶与桶通过`node`节点的`next`指针相连，由`before_begin`指针记录首地址。这样的好处是便于高效迭代。迭代时，像迭代单链表的方式一样，从`before_begin`出发，可以在O(n)时间内迭代完哈希表内的所有元素。（其中n为哈希表中元素的数量，即`element_count`或`std::unordered_map::size()`）

![unordered_map (3)](https://raw.githubusercontent.com/Zacharier/gdb-debug/master/assets/img/unordered_map.png)

## Python扩展

### Python API

这里根据gdb的Python API做一个简要的基本介绍。更详细的内容可参考：https://sourceware.org/gdb/current/onlinedocs/gdb/Python-API.html#Python-API 

#### Symbol

`gdb.Symbol`代表调试时候的源码中的各种符号，如变量名，函数名，类名等等。这些信息都存储在符号表中并且在运行时不可变（虽然C++函数名会在编译时被`mangled`）。

```C++
int main() {
    int a = 0;
    return 0;
}
```

在gdb的键入`pi`(Python交互模式)命令进入Python交互模式：

```
(gdb) pi
>>> sym_main.print_name
'main()'
>>> sym_main.is_function
True
>>> sym_a, _ = gdb.lookup_symbo('a')
>>> sym_a.is_variable
True
>>> sym_a.print_name
'a'
```

#### Value

`gdb.Value`代表gdb调试时候的一个`value`。可以是变量（包括全局/静态变量）、指针、引用、表达式、字面量或者函数。`value`可以支持基本的加减乘除运算，其结果仍然是一个`value`对象，或者一些二元操作。

```C++
void test() {
    puts("test\n");
}
```
`pi`模式下：

```
(gdb) pi
>>> sym, _ = gdb.lookup_symbol('test')
>>> val = sym.value(gdb.selected_frame())
>>> val()
test

<gdb.Value object at 0xb5aacec0>
```

#### Type

`gdb.Type`代表gdb调试时候的对象类型。可以是基本类型，也可以是各种符合类型，以及stl的模板类型。

```C++
std::string s("Hello, World");
```

`pi`模式下：

```
>>> sym, _ = gdb.lookup_symbol('s')
>>> sym.type.name
'std::__cxx11::string'
```

#### Command
`gdb.Command`用来实现一个新gdb命令，支持在gdb中直接调用，和gdb内置命令的并无区别。
一个简单的来自官方的例子：
hello_world.py：
```Python
class HelloWorld (gdb.Command):
  """Greet the whole world."""

  def __init__ (self):
    super (HelloWorld, self).__init__ ("hello-world", gdb.COMMAND_USER)

  def invoke (self, arg, from_tty):
    print "Hello, World!"

HelloWorld ()
```
在gdb中使用如下：
```
(gdb) source hello_world.py
(gdb) hello-world
Hello, World!
```

Python API的基本的概念就介绍到此，这已经足够我们写一个使用的扩展工具了。

### View扩展

为gdb编写扩展`v`命令

#### 加载

1. 直接在gdb中使用`source`命令加载扩展脚本，如：`source view.py`

2. 自动加载，修改`gdbinit`文件，如`/etc/gdb/gdbinit`或者当前用户的`~/.dbinit`添加如下内容：

   ```Python
   python
   import sys
   sys.path.insert(0, '/xx/user/xxxx')
   import see
   end
   ```

完成加载后可通过`help`命令验证：

```
(gdb) help v
    Usage: v [OPTION]... SYMBOL...
    Options:
            /l    calculate length/size of object.
            /i    return the item at index of string/vector.
            /f    find the corresponding value by KEY.
```



#### 使用

源码test.cc:

```C++
#include <stdio.h>
#include <stdlib.h>

#include <string>
#include <unordered_map>
#include <vector>

int main(int argc, char* argv[]) {
    std::string s("Hello, World");

    std::vector<std::string> vec = {"hello", "ciao", "hola"};

    std::unordered_map<int, int> map = {
        {1, 2},
        {3, 4},
        {5, 6},
    };

    return 0;
}
```

通过`g++ -g`编译后，使用gdb调试暂停至`return 0`处，通过`v`命令调试如下：

```
(gdb) v s
<address: 0xbefff380, content: {'Hello, World'}>
(gdb) v /l s
12
(gdb) v /i s 6
32 ' '
(gdb) v vec
<address: 0x2b058, content: {"hello", "ciao", "hola"}>
(gdb) v /l vec
3
(gdb) v /i vec 2
"hola"
(gdb) v map
{5: 6, 3: 4, 1: 2}
(gdb) v /l map
3
(gdb) v /f map 5
6
```



#### 扩展源码

view.py

```Python
import functools
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

    def at(self, val, _):
        raise UnimplementedError('/i')

    def length(self, val, _):
        raise UnimplementedError('/l')

    def find(self, _):
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
        if i >= self.length(val):
            raise OutBoundError(i)
        return (ptr + i).dereference()

    def length(self, val):
        ptr = val['_M_dataplus']['_M_p']
        head = ptr.cast(gdb.lookup_type('size_t').pointer()) - 3;
        # capacity = (head + 1).dereference()
        # refcount = (head + 2).dereference()
        # return ptr, length, capacity, refcount
        length = head.dereference()
        return int(length)

    def to_string(self, val):
        ptr = val['_M_dataplus']['_M_p']
        length = self.length(val)
        iterator = ContiguousIterator(ptr, ptr + self.length(val))
        content = ''.join(map(chr,iterator))
        ptr = ptr.cast(gdb.lookup_type('void').pointer())
        return '<address: %s, content: {%s}>' % (ptr, repr(content))


class StdCxx11StringView(StdStringView):
    def __init__(self):
        super().__init__('std::__cxx11::string')

    def length(self, val):
        return int(val['_M_string_length'])


class StdVectorView(View):
    def __init__(self):
        super().__init__('std::vector')

    def at(self, val, i):
        i = int(i)
        ptr = val['_M_impl']['_M_start']
        if i >= self.length(val):
            raise OutBoundError(i)
        return (ptr + i).dereference()

    def length(self, val):
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

    def length(self, val):
        return int(val['_M_h']['_M_element_count'])

    def to_string(self, val):
        s = ', '.join(['%s: %s' % pair for pair in self.items(val)])
        return '{%s}' % s


class Viewer(gdb.Command):
    """\
    Usage: v [OPTION]... SYMBOL...
    Options:
            /l    calculate length/size of object.
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
            '/l': view.length,
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
        except UnimplementedError:
            print("Unimpelemeted Error: %s'" % e)
        except NotFoundError as e:
            print("Not Found Error: %s" % e)
        except ViewError as e:
            print("Uncaught Error: %s" % e)


Viewer()
```

