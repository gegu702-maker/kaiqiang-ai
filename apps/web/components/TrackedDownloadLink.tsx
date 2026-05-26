"use client";

import { AnchorHTMLAttributes, ReactNode } from "react";

import { trackEvent } from "@/lib/analytics";

type TrackedDownloadLinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  taskId?: string;
  productName?: string;
  children: ReactNode;
};

export function TrackedDownloadLink({ taskId, productName, onClick, children, ...props }: TrackedDownloadLinkProps) {
  return (
    <a
      {...props}
      onClick={(event) => {
        trackEvent("download_video", {
          task_id: taskId,
          product_name: productName,
          href: typeof props.href === "string" ? props.href : undefined,
        });
        onClick?.(event);
      }}
    >
      {children}
    </a>
  );
}
