from ctypes import *
from ctypes.wintypes import *
from vkcontextmanager import VkContextManager
import time

WNDPROCTYPE = WINFUNCTYPE(c_int, HWND, c_uint, WPARAM, LPARAM)

WS_EX_APPWINDOW = 0x40000
WS_OVERLAPPEDWINDOW = 0xcf0000
WS_CAPTION = 0xc00000
WS_CLIPSIBLINGS = 0x04000000
WS_CLIPCHILDREN = 0x02000000
WS_VISIBLE = 0x10000000

SW_SHOWNORMAL = 1
SW_SHOW = 5

CS_HREDRAW = 2
CS_VREDRAW = 1

CW_USEDEFAULT = 0x80000000

WM_DESTROY = 2
WM_QUIT = 0x0012
WM_KEYDOWN = 0x0100
WM_TIMER = 0x0113

WHITE_BRUSH = 0

PM_REMOVE = 0x0001

VK_ESCAPE = 0x1B

IDI_WINLOGO = 32517
IDC_ARROW = 32512

class WNDCLASSEX(Structure):
    _fields_ = [("cbSize", c_uint),
                ("style", c_uint),
                ("lpfnWndProc", WNDPROCTYPE),
                ("cbClsExtra", c_int),
                ("cbWndExtra", c_int),
                ("hInstance", HANDLE),
                ("hIcon", HANDLE),
                ("hCursor", HANDLE),
                ("hBrush", HANDLE),
                ("lpszMenuName", LPCWSTR),
                ("lpszClassName", LPCWSTR),
                ("hIconSm", HANDLE)]

def PyWndProcedure(hWnd, Msg, wParam, lParam):
    if Msg == WM_DESTROY:
        windll.user32.PostQuitMessage(0)
    elif Msg == WM_KEYDOWN:
        if wParam == VK_ESCAPE:
            windll.user32.PostQuitMessage(0)
    else:
        try:
            return windll.user32.DefWindowProcW(hWnd, Msg, wParam, c_longlong(lParam))
        except:
            pass

    return 0

class Win32Window:
    def __init__(self, hWnd):
        self.hWnd = hWnd

    def winId(self):
        return self.hWnd

def win32_vk_main(vulkan_render_fct, redraw_interval_ms):

    WndProc = WNDPROCTYPE(PyWndProcedure)
    hInst = windll.kernel32.GetModuleHandleW(0)
    wclassName = u'Hello Vulkan Win32 Class'
    wname = u'Hello Vulkan Win32 Window'

    wndClass = WNDCLASSEX()
    wndClass.cbSize = sizeof(WNDCLASSEX)
    wndClass.style = CS_HREDRAW | CS_VREDRAW
    wndClass.lpfnWndProc = WndProc
    wndClass.cbClsExtra = 0
    wndClass.cbWndExtra = 0
    wndClass.hInstance = hInst
    wndClass.hIcon = 0
    wndClass.hCursor = windll.user32.LoadCursorW(0, IDC_ARROW)
    wndClass.lpszMenuName = 0
    wndClass.hbrBackground = windll.gdi32.GetStockObject(WHITE_BRUSH)
    wndClass.lpszClassName = wclassName
    wndClass.hIconSm = windll.user32.LoadIconW(0, IDI_WINLOGO)

    regRes = windll.user32.RegisterClassExW(byref(wndClass))
    windll.user32.AdjustWindowRect( RECT(0,0,640,480), WS_OVERLAPPEDWINDOW, 0)
    hWnd = windll.user32.CreateWindowExW(0,wclassName,wname, WS_CLIPSIBLINGS | WS_CLIPCHILDREN | WS_VISIBLE | WS_OVERLAPPEDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT, 640, 480,0,0,hInst,0)

    if not hWnd:
        print('Failed to create window')
        exit(0)
    print('ShowWindow', windll.user32.ShowWindow(hWnd, SW_SHOW))
    print('UpdateWindow', windll.user32.UpdateWindow(hWnd))

    msg = MSG()
    lpmsg = pointer(msg)

    print('Creating Vulkan Context')
    with VkContextManager(VkContextManager.VKC_INIT_PIPELINE, surface_type = VkContextManager.VKC_WIN32, widget=Win32Window(hWnd)) as vkc:
        print('Entering message loop')
        set_timer = True
        redraw = True
        while True:
            quit = False
            while windll.user32.PeekMessageW(lpmsg, 0, 0, 0, PM_REMOVE) != 0:
                if msg.message == WM_QUIT:
                    quit = True
                    break

                if msg.message == WM_TIMER and msg.wParam == 1:
                    redraw = True

                windll.user32.TranslateMessage(lpmsg)
                windll.user32.DispatchMessageW(lpmsg)

            if quit:
                break

            if redraw:
                vulkan_render_fct(vkc)
                redraw = False

            if set_timer:
                success = windll.user32.SetTimer(hWnd, 1, redraw_interval_ms, 0)
                set_timer = False

        print('done.')

if __name__ == "__main__":
    print("Win32 Application in python")
    def no_render(vkc):
        pass
    win32_vk_main(no_render)