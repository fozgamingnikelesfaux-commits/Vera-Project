using UnityEngine;
using System;
using System.Runtime.InteropServices;

public class TransparentWindow : MonoBehaviour
{
    // Importer les fonctions de l'API Windows
    [DllImport("user32.dll")]
    private static extern IntPtr GetActiveWindow();

    [DllImport("user32.dll")]
    private static extern int SetWindowLong(IntPtr hWnd, int nIndex, uint dwNewLong);

    [DllImport("user32.dll")]
    private static extern int SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int x, int y, int cx, int cy, uint uFlags);

    [DllImport("dwmapi.dll")]
    private static extern int DwmExtendFrameIntoClientArea(IntPtr hWnd, ref MARGINS pMarInset);

    // Constantes pour les styles de fenêtre
    private const int GWL_STYLE = -16;
    private const uint WS_POPUP = 0x80000000;
    private const uint WS_VISIBLE = 0x10000000;

    // Constante pour la position de la fenêtre
    private static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);

    // Structure pour les marges DWM
    private struct MARGINS
    {
        public int cxLeftWidth;
        public int cxRightWidth;
        public int cyTopHeight;
        public int cyBottomHeight;
    }

    void Start()
    {
#if !UNITY_EDITOR // Ne pas exécuter ce code dans l'éditeur Unity
        IntPtr hWnd = GetActiveWindow();

        // Rendre le fond transparent
        MARGINS margins = new MARGINS { cxLeftWidth = -1 };
        DwmExtendFrameIntoClientArea(hWnd, ref margins);

        // Changer le style de la fenêtre pour la rendre sans bordures
        SetWindowLong(hWnd, GWL_STYLE, WS_POPUP | WS_VISIBLE);

        // Optionnel : Garder la fenêtre au premier plan
        // SetWindowPos(hWnd, HWND_TOPMOST, 0, 0, 0, 0, 0);
#endif
    }
}
