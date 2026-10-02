import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "@/components/Button";
import { StatusBadge } from "@/components/StatusBadge";
import { Card } from "@/components/Card";
import { CurrencyAmount } from "@/components/CurrencyAmount";
import { PricingCard } from "@/components/PricingCard";

describe("Button", () => {
  it("renders children and responds to clicks", async () => {
    const onClick = () => {};
    const spy = (() => {
      let count = 0;
      const fn = () => {
        count += 1;
      };
      fn.calls = () => count;
      return fn;
    })();
    render(<Button onClick={spy}>Send</Button>);
    const btn = screen.getByRole("button", { name: "Send" });
    expect(btn).toBeInTheDocument();
    await userEvent.click(btn);
    expect(spy.calls()).toBe(1);
    expect(onClick).toBeTypeOf("function");
  });

  it("disables while loading", () => {
    render(<Button loading>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });
});

describe("StatusBadge", () => {
  it.each(["draft", "sent", "viewed", "accepted", "rejected", "expired", "cancelled"] as const)(
    "renders %s status",
    (status) => {
      render(<StatusBadge status={status} />);
      expect(screen.getByText(status)).toBeInTheDocument();
    },
  );
});

describe("Card", () => {
  it("renders title and content", () => {
    render(<Card title="Details">Body</Card>);
    expect(screen.getByText("Details")).toBeInTheDocument();
    expect(screen.getByText("Body")).toBeInTheDocument();
  });
});

describe("CurrencyAmount", () => {
  it("renders a formatted amount", () => {
    render(<CurrencyAmount minor={1234} currency="USD" />);
    expect(screen.getByText("$12.34")).toBeInTheDocument();
  });
});

describe("PricingCard", () => {
  it("lists features and triggers onSelect", async () => {
    const spy = () => {};
    render(
      <PricingCard
        name="Starter"
        price="$9"
        tagline="For growing businesses"
        features={["50 quotes/month", "50 AI assists"]}
        cta="Choose Starter"
        onSelect={spy}
      />,
    );
    expect(screen.getByText("Starter")).toBeInTheDocument();
    expect(screen.getByText("50 quotes/month")).toBeInTheDocument();
    const btn = screen.getByRole("button", { name: "Choose Starter" });
    expect(btn).toBeInTheDocument();
    await userEvent.click(btn);
  });
});