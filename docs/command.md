# 命令

本文介绍一些常用命令的基本用法。

gdb的命令一般以单词前一个或多个字母作为其别名，也支持通过`<Tab>`键补全。另外，可以通过`<RET>`键重放上一条命令。

#### 说明事项

1. 下文涉及到的命令均可以在gdb中使用`help command`命令获取到更详细的帮助信息，亦可通过`help all`查看所有命令的帮助信息。

2. 下文代码示例采用的机器型号和软件版本如下：

   *Linux raspberrypi ... armv7l GNU/Linux*  

   *GNU gdb (Raspbian 8.2.1-2) 8.2.1*

   *gcc version 8.3.0 (Raspbian 8.3.0-6+rpi1)* 

## Demo

下文要用到的代码（hello.cc ）

```C++
#include <stdio.h>
#include <string>
#include <thread>

int main(int argc, char* argv[]) {
    int ints[] = {10, 9, 8, 7, 6, 5, 4, 3, 2, 1};
    const char* string = "hello, world";
    const char* strings[] = {"a", "b", "c", "d", "e", "f", "g", "h", "i", "j"};
    bool running = true;
    std::thread t([&running]() {
       while (running)
           printf("background thread is running ...\n");
    });
    printf("end\n");
    running = false;
    t.join();
    int f = sum(1, 2);
    printf("%d\n", f);
    return 0;
}

int sum(int a, int b) {
    int c = a + b;
    return c;
}
```

编译：`g++ -o hello -std=c++11 -g hello.cc -lpthread`

## 启动

### file

在gdb中加载可执行程序，执行命令`file BINARY`指定调试的程序。如果是本地程序推荐直接通过`gdb BINARY`加载。

### attach

和`file`命令类似，用来调试服务类程序，通过`attach PID`即可调试正在运行中的程序。

### set args

设置程序启动参数，如`ls -l /usr/bin`，在gdb中即为`set args -l /usr/bin`

### set env

设置程序的环境变量，如`set env LD_LIBRARY_PATH=./so`。

### run

简写`r`，在gdb中开始运行待调试的程序。另，该命令支持类似`shell`的输入（`<`）输出（`>`或`>>`）重定向功能。

**注意**：如果没有设置断点或者其他阻断的行为，程序将一直运行直到结束。

### start

和`r`类似，不同的是`start`命令开始运行后会自动暂停在main函数的起始处。

## 数据

### print

简写`p`，可以用来打印变量、数组、结构体和对象等表达式的值，如`p EXP`使用简单这里不再赘述。下面主要讲一下连续内存空间的数值打印，比如数组：

`print ARR@NUM`打印`arr`的数组的前NUM个元素。

比如对于代码片段：

```c++
int ints[] = {10, 9, 8, 7, 6, 5, 4, 3, 2, 1};
const char* string = "hello, world";
```

gdb输出如下：

```shell
(gdb) p ints[0]@10
$1 = {10, 9, 8, 7, 6, 5, 4, 3, 2, 1}
(gdb) p *ints@10
$2 = {10, 9, 8, 7, 6, 5, 4, 3, 2, 1}
(gdb) p string[0]@10
$3 = "hello, wor"
(gdb) p *string@10
$4 = "hello, wor"
```

此外，gdb还支持格式化打印，比如`p/x 3`打印数字`3`的16进制。更详细的格式化打印见下文`x`命令。

**注意**：在gdb7.0开始，gdb自带了pretty-printers功能，支持可视化的打印数组和C++ STL容器等。使用`p`命令即可对表达式进行自动格式化并输出，但该可视化的输出并不总是符合我们预期。

### x

格式为：`x/FMT ADDR`，命令`print`的增强版。指的是按照指定的`FMT`去打印`ADDR`指针所指的内存的内容。

举例说明： `x/10dw ints`。意思为打印数组`ints`的前10个元素。

`d`表示用十进制打印。除`d`以外还有`x`、`u`、`f`、`c`、`s`分别代表16进制、无符号整数、浮点数、字符和字符串，这里和C语言的`printf`函数的格式化字符一致，只是前者没有前导字符`%`。

`w`代表以4字节为一个元素的宽度。其他宽度还有：`b`为1字节、`h`为2个字节、`g`为8字节。比如我们的`ints`数组如果每个元素是8字节如`long long int longs[] = {...}`，则打印方式为：`x/10dg longs`

gdb输出示例如下：

```shell
(gdb) x/10dw ints
0xbefff3f4:	10 9	8	7
0xbefff404:	6	 5	4	3
0xbefff414:	2	 1
(gdb) x/10x ints
0xbefff3f4:	0x0000000a	0x00000009	0x00000008	0x00000007
0xbefff404:	0x00000006	0x00000005	0x00000004	0x00000003
0xbefff414:	0x00000002	0x00000001
(gdb) x/d ints
0xbefff3f4:	10
(gdb) x ints
0xbefff3f4:	10
(gdb) x/s string
0x105e4:	"hello, world"
(gdb) x/5c string
0x105e4:	104 'h'	101 'e'	108 'l'	108 'l'	111 'o'
```

**注意**：`FMT`可以部分省略或者全部省略。则默认打印的元素数量为1，打印的元素格式和宽度默认是用上一次的值。

### display

用法和`p`一致，不同的是每暂停一次，都会自动打印`display`的表达式。可以通过`undisplay NUM`取消。

### dump

一种典型的使用场景是一个请求使服务崩溃生成了core文件。我们可以通过`dump`命令在core文件中提取出使得服务崩溃的原始请求的二进制内容到本地，再对该内容加以分析，以便得出崩溃的原因。使用示例如下：

```shell
(gdb) dump binary memory ints.dat ints ints+10
```

上面命令的意思是以二进制的格式`dump`出起始地址`ints`到结束地址`ints+10`之间的内存到当前的目录下的`ints.dat`文件中。使用`od`命令验证输出：

```shell
$ od -i ints.dat 
0000000          10           9           8           7
0000020           6           5           4           3
0000040           2           1
0000050
```

## 状态

### info

`info args`显示当前栈帧（函数）的参数和其对应的值。

`info locals`显示当前栈帧（函数）的局部变量和其对应的值。

`info reg`显示当前寄存器列表和值。

`info break`显示当前设置的所有断点和观察点。

`info watch`只显示观察点。

`info thread`显示线程列表。

`info frame`打印当前栈帧信息。

### show

`show env`查看设置的环境变量。

`show args`查看程序启动参数。

## 堆栈

### backtrace

简写为`bt`，别名为`where`。打印当前的调用栈，一般是从当前调用处的栈帧到`main`函数栈帧，如：

```shell
(gdb) where
#0  strlen () at ../sysdeps/arm/armv6/strlen.S:26
#1  0xb6c9053c in __GI__IO_puts (str=0x1091c "end") at ioputs.c:35
#2  0x00010818 in main (argc=1, argv=0xbefff564) at hello.cc:15
```

其中`#`后面的数字代表栈帧编号。

### frame

简写为`f`，根据栈帧编号选择一个栈帧。

```shell
(gdb) f 2
#2  0x00010818 in main (argc=1, argv=0xbefff564) at hello.cc:13
```

### return

使当前函数立即返回到被调用函数，可以带一个表达式参数，代表返回值。

## 断点

### break

简写`b`。在程序的某处设下断点，可以是文件+行号，函数名（C++中需要明确给出namespace和class，如：db::Table::OpenUrl）或者明确的函数首地址，亦或是指令地址，如：

```shell
(gdb) b main
Breakpoint 7 at 0x10750: file hello.cc, line 15.
(gdb) b hello.cc:17
Breakpoint 8 at 0x1077c: file hello.cc, line 17.
(gdb) b *main
Breakpoint 9 at 0x1073c: file hello.cc, line 14.
(gdb) b *0x10748
Breakpoint 10 at 0x10748: file hello.cc, line 14.
(gdb) info b
Num     Type           Disp Enb Address    What
7       breakpoint     keep y   0x00010750 in main(int, char**) at hello.cc:15
8       breakpoint     keep y   0x0001077c in main(int, char**) at hello.cc:17
9       breakpoint     keep y   0x0001073c in main(int, char**) at hello.cc:14
10      breakpoint     keep y   0x00010748 in main(int, char**) at hello.cc:14
```

**注意**：打印指令级的断点需要在表达式开始处加入`*`字符

### watch

设置观察点，以检测一个表达式是否发生改变。如果观察得是变量的话，指的是变量的值。如果的是指针，则指的是指针本身的值是否发生改变。

另有`awatch`由表达式读写触发，`rwatch`只读触发。

```shel
int ints[] = {10, 9, 8, 7, 6, 5, 4, 3, 2, 1};
(gdb) watch *ints@10
Watchpoint 22: *ints@10
```

## 运行

### next

简写`n`，单步执行。可以带一个行数作为参数。例如`next`即等价于`next 1`。`next 2`为执行两行代码并暂停。

```shell
6	    int ints[] = {10, 9, 8, 7, 6, 5, 4, 3, 2, 1};
(gdb) n 2
8	    const char* strings[] = {"a", "b", "c", "d", "e", "f", "g", "h", "i", "j"};
```

上述为执行`6`、`7`行共两行代码后暂停在`8`行开始处。

**注意**：当遇到函数调用时，不会进入该函数内部。

### call

调用一个函数，如：

```shell
(gdb) call printf("%s\n", "hello, gdb")
hello, gdb
$4 = 11
```

输出为格式化字符以及`printf`函数的返回值`11`代表打印的字符数。

### step

简写`s`，进入函数。

### finish

简写`fin`，执行完当前函数并返回到主调函数。

### until

直到执行到某一行时暂停，如`until 15`，即为执行到第`15`行时暂停。非常适合用来跳出各种语句块。

## 线程

### thread

简写`t`，命令`thread ID`意为切换到编号为ID的线程，其中ID可以通过`info thread`获取。

`thread apply ID command`将gdb命令应用到ID所在的线程。其中ID也可以用`all`替代，指的是应用命令到所有的线程，如：

```shell
(gdb) thread apply 2 b 11

Thread 2 (Thread 0xb6c31450 (LWP 4058)):
Breakpoint 2 at 0x108b0: file hello.cc, line 11.
(gdb) thread apply all bt

Thread 2 (Thread 0xb6c31450 (LWP 4520)):
#0  __GI___libc_write (nbytes=33, buf=0xb63005b8, fd=1) at ..
# ....
#16 0xb6d09578 in ?? () at ../sysdeps/unix/sysv/linux/arm/clone.S:73 from /lib/arm-linux-gnueabihf/libc.so.6
Backtrace stopped: previous frame identical to this frame (corrupt stack?)

Thread 1 (Thread 0xb6ff7010 (LWP 4517)):
#0  main (argc=1, argv=0xbefff564) at src/hello.cc:15
(gdb) info thread
  Id   Target Id                            Frame 
  1    Thread 0xb6ff7010 (LWP 4055) "hello" main (argc=1, argv=0xbefff564) at hello.cc:14
* 2    Thread 0xb6c31450 (LWP 4058) "hello" <lambda()>::operator()(void) const (__closure=0x2805c) at hello.cc:10
```

多线程调试建议配合`set scheduler-locking on`来使用。意为锁定其他线程，只允许当前线程执行和进行命令调试。默认为`off`，代表所有线程都可以正常运行。在一个拥有成百上千个线程的进程里，可以通过启用该开关来调试某个具体的线程。

## 汇编

`disassemble`

简写`disas`，显示当前代码的汇编指令。尤其在没有源码的场景下非常有用。

`disas /s`混合模式，输出汇编指令和相应的源码，如：

```C++
(gdb) disas /s sum
Dump of assembler code for function sum(int, int):
c++:
20	int sum(int a, int b) {
   0x000109c0 <+0>:	  push	{r11}		; (str r11, [sp, #-4]!)   // 保存上一个栈帧的帧寄存器
   0x000109c4 <+4>:	  add	r11, sp, #0                         // 复用r11指向当前栈寄存器
   0x000109c8 <+8>:	  sub	sp, sp, #20                         // 开辟20个字节空间（栈向下增长）
   0x000109cc <+12>:	str	r0, [r11, #-16]                     // r0（即实参a）到r11[-16]
   0x000109d0 <+16>:	str	r1, [r11, #-20]	; 0xffffffec        // r1（即实参b）到r11[-20]

21	    int c = a + b;
   0x000109d4 <+20>:	ldr	r2, [r11, #-16]                     // 求和。。。
   0x000109d8 <+24>:	ldr	r3, [r11, #-20]	; 0xffffffec
   0x000109dc <+28>:	add	r3, r2, r3
   0x000109e0 <+32>:	str	r3, [r11, #-8]

22	    return c;
   0x000109e4 <+36>:	ldr	r3, [r11, #-8]                       // 求和结果加载到r3

23	}
   0x000109e8 <+40>:	mov	r0, r3                               // 赋值给r0，用作函数返回值
   0x000109ec <+44>:	add	sp, r11, #0                          // 更新sp到r11
   0x000109f0 <+48>:	pop	{r11}		; (ldr r11, [sp], #4)        // 恢复上一个栈帧值
   0x000109f4 <+52>:	bx	lr                                   // 跳转到lr（lr对应函数返回地址）
End of assembler dump.
```

**注意**：上面为一段未经优化的**ARM**汇编指令+源码示例（主要指令行尾均作有注释）

调试汇编程序的命令时，只需在调试命令后新增一个字符`i`即可，如`ni`和`si`。打断点则在表达式前边加`*`，如`b *main`和`b *0x1234`。除此之外，调试的方式和源码方式并无不同。

