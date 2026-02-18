import type { Metadata } from "next";
import "@livekit/components-styles";

export const metadata: Metadata = {
  title: "Georgian Voice AI",
  description: "Real-time Georgian voice conversation platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ka">
      <body
        style={{
          margin: 0,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          backgroundColor: "#0a0a0a",
          color: "#ededed",
          minHeight: "100vh",
        }}
      >
        {children}
      </body>
    </html>
  );
}
