# 扩展

gdb允许用户通过Python或Guile（Scheme）扩展来增强gdb的调试能力，其中仅Python扩展是gdb默认启用的，所以这里单讲如何使用Python编写gdb扩展。

gcc 7.x以后，内置了一个新的功能——[Pretty-Printer](https://sourceware.org/gdb/current/onlinedocs/gdb/Pretty_002dPrinter-Introduction.html#Pretty_002dPrinter-Introduction)，该功能可以非常『漂亮』的打印数组、结构体和class的内容，尤其是对C++容器的支持。和`print`命令无缝结合，让调试更加的简单。遗憾的是该功能比较单一，只是美化了输出，对于较大数据量会进行截断，并隐藏了内存地址和其他一些重要的调试信息。

鉴于此，本文将通过编写一个实用的gdb扩展来支持在gdb中对C++容器常用调试操作，可以作为`Pretty-Printer`的增强。

编写针对于C++容器的Python扩展需要两方面知识：一是足够了解C++容器的源码实现；二是熟悉gdb提供的Python API。因此我们从C++容器开始一一讲解。

## C++容器
这里介绍如下三种常用容器的源码实现：

1. `std::string`
2. `std::vector`
3. `std::unordered_map`

这里采用的源码版本为gcc 8.3.0，源码地址：http://mirror.hust.edu.cn/gnu/gcc/gcc-8.3.0/

**注意**：gcc在版本4.x以后，容器的内存布局甚至是成员变量名均少有变化，因此该部分介绍的内容可以适用于目前绝大多数的gcc版本。在不同版本或者ABI下有较大差异的实现下文也会单独注明

### std::string

`std::string`的内部持有一块连续性内存，一般的实现为内部一个成员指针`char*`指向一段动态申请的内存，并同时内部记录当前字符串的长度（length），以及这段内存的大小，通常称为容量（capacity）。如果内存不够则进行扩展（resize/reserve），即申请一段新的内存，将旧内存上的数据拷贝过来，释放旧内存。最终这段动态申请的内存在析构函数中释放。

该版本的实现存在两个版本，通过`_GLIBCXX_USE_CXX11_ABI`宏来区分不同的版本。

在gcc4.x以后string的实现基于引用计数的COW（Copy On Write），内存布局如下：

![string_cow](https://raw.githubusercontent.com/Zacharier/gdb-debug/master/assets/img/string_cow.png)

在gcc7.x以上，默认启用C++11 ABI宏的本地Buff实现，内存布局如下：

![string_buf](https://raw.githubusercontent.com/Zacharier/gdb-debug/master/assets/img/string_buf.png)

### std::vector

`std::vector`的实现和`std::string`基本一致，这里不多介绍，内存布局如下：

![vector](https://raw.githubusercontent.com/Zacharier/gdb-debug/master/assets/img/vector.png)

### std::unordered_map

`std::unordered_map`即哈希表，内部由一个桶数组和链表实现，即经典的链式哈希表。内存布局如下

**注意**：该实现版本将所有元素通过`next`指针首尾相连，便于高效迭代。迭代方式和普通单链表一样，从`before_begin`出发，在`O(n)`时间可以内完成迭代操作。（其中n为哈希表中元素的数量，即`element_count`或`std::unordered_map::size()`）

![unordered_map (3)](https://raw.githubusercontent.com/Zacharier/gdb-debug/master/assets/img/unordered_map.png)

## Python API

gdb会将调试时的各种信息根据源码抽象成统一的Python对象，我们可以根据源码结构通过gdb提供的Python API对该对象进行各种操作，如：变量/成员访问、解指针/引用、地址偏移、数组/链表遍历、寄存器状态、栈回溯等各种功能。因此要编写扩展，必须先了解Python API。

这里对Python API做一个简要的基本介绍。更详细的内容可参考官方文档：https://sourceware.org/gdb/current/onlinedocs/gdb/Python-API.html#Python-API 

### Symbol

`gdb.Symbol`代表调试时源码中的各种符号，如变量名，函数名，类名等等。这些信息都存储在符号表中并且在运行时不可变（虽然C++函数名会在编译时被`mangled`）。

示例：

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

### Value

`gdb.Value`代表gdb调试时候的一个`value`。可以是变量（包括全局/静态变量）、指针、引用、表达式、字面量或者函数。`value`可以支持基本的加减乘除运算，其结果仍然是一个`value`对象，或者一些二元操作。

示例：

```C++
void test() {
    puts("test\n");
}
```
`pi`模式：

```
(gdb) pi
>>> sym, _ = gdb.lookup_symbol('test')
>>> val = sym.value(gdb.selected_frame())
>>> val()
test

<gdb.Value object at 0xb5aacec0>
```

### Type

`gdb.Type`代表gdb调试时候的对象类型。可以是基本类型，也可以是各种符合类型，以及stl的模板类型。

示例：

```C++
std::string s("Hello, World");
```

`pi`模式：

```
(gdb) pi
>>> sym, _ = gdb.lookup_symbol('s')
>>> sym.type.name
'std::__cxx11::string'
```

### Command
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

Python API的基本的概念就介绍到此，这足够我们写一个gdb扩展了。

## Python扩展

gdb有一个`examine`命令——`x`。`x`命令专门用来查看指针所指向的内容，非常强大，可惜却无法应用到C++容器中。我们仿照`x`来实现一个新的gdb命令`View`——`v`。该命令通过Python扩展实现主要功能有：

*  获取C++容器的各种内部信息，包括内容、首地址、长度等信息
*  支持查找、下标访问等行为

### 代码

gdb扩展`v`命令Python代码实现见 [view.py](https://github.com/Zacharier/gdb-debug/blob/master/codes/view.py "view.py")。实现涉及到的基本概念上文均有讲解，这里不再赘述。

该扩展支持如下功能：

1. 打印容器的内容
2. 打印容器的大小
3. 通过下标访问容器元素
4. 通过key访问关联容器的value

### 加载

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

示例test.cc:

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

通过`g++ -g`编译后使用gdb调试，暂停至`return 0`处，使用`v`命令：

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
