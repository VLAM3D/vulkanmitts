from ctypes import *
from ctypes.wintypes import *

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

WHITE_BRUSH = 0

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
    else:
        return windll.user32.DefWindowProcW(hWnd, Msg, wParam, c_void_p(lParam))
    return 0
  
def main():
	WndProc = WNDPROCTYPE(PyWndProcedure)
	hInst = windll.kernel32.GetModuleHandleW(0)
	wclassName = 'My Python Win32 Class'
	wname = 'My test window'
	
	wndClass = WNDCLASSEX()
	wndClass.cbSize = sizeof(WNDCLASSEX)
	wndClass.style = CS_HREDRAW | CS_VREDRAW
	wndClass.lpfnWndProc = WndProc
	wndClass.cbClsExtra = 0
	wndClass.cbWndExtra = 0
	wndClass.hInstance = hInst
	wndClass.hIcon = 0
	wndClass.hCursor = 0
	wndClass.hBrush = windll.gdi32.GetStockObject(WHITE_BRUSH)
	wndClass.lpszMenuName = 0
	wndClass.lpszClassName = wclassName
	wndClass.hIconSm = 0
	
	regRes = windll.user32.RegisterClassExW(byref(wndClass))
	
	hWnd = windll.user32.CreateWindowExW(0,wclassName,wname, WS_CLIPSIBLINGS | WS_CLIPCHILDREN | WS_VISIBLE | WS_OVERLAPPEDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT, 300,300,0,0,hInst,0)
	
	if not hWnd:
		print('Failed to create window')
		exit(0)
	print('ShowWindow', windll.user32.ShowWindow(hWnd, SW_SHOW))
	print('UpdateWindow', windll.user32.UpdateWindow(hWnd))

	msg = MSG()
	lpmsg = pointer(msg)

	print('Entering message loop')
	while windll.user32.GetMessageW(lpmsg, 0, 0, 0) != 0:
		windll.user32.TranslateMessage(lpmsg)
		windll.user32.DispatchMessageW(lpmsg)

	print('done.')
	
if __name__ == "__main__":
    print("Win32 Application in python")
    main()