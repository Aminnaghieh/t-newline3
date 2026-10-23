import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

export const metadata: Metadata = {
  title: "سوپر ایجنت لیارا | Liara Super Agent",
  description:
    "محیط اختصاصی سوپر ایجنت هوشمند برای مشتریان پلتفرم ابری لیارا — استقرار، مانیتورینگ، عیب‌یابی و مدیریت سرویس‌ها با هوش مصنوعی",
  keywords: ["لیارا", "Liara", "SRE", "DevOps", "هوش مصنوعی", "PaaS", "ایجنت هوشمند"],
  icons: {
    icon:
      "data:image/svg+xml," +
      encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#87fcc4"/><stop offset="1" stop-color="#28c1f5"/></linearGradient></defs><rect width="32" height="32" rx="8" fill="#161b18"/><path d="M9 8h4v12h9v4H9z" fill="url(#g)"/></svg>`
      ),
  },
};

export const viewport: Viewport = {
  themeColor: "#161b18",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fa" dir="rtl" suppressHydrationWarning>
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css"
        />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Farsi-Digits/Vazirmatn-FD-font-face.css"
        />
      </head>
      <body
        className="antialiased bg-background text-foreground"
        style={
          {
            "--font-app": "Vazirmatn, Vazirmatn FD, Tahoma",
            "--font-mono-app": "SFMono-Regular, Consolas, 'Liberation Mono', monospace",
          } as React.CSSProperties
        }
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
