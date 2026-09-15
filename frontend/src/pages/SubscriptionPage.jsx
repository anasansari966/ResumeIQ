import { useMemo, useState } from "react";
import { Check, Crown } from "lucide-react";
import ConfirmModal from "../components/ConfirmModal";

const PLANS = {
  free: {
    name: "Free",
    monthly: 0,
    yearly: 0,
    features: ["2 resumes", "5 job searches/day", "No ATS scoring", "No AI generation"],
  },
  basic: {
    name: "Basic",
    monthly: 299,
    yearly: 2499,
    features: ["10 resumes", "50 job searches/day", "ATS scoring", "5 AI generations/month"],
    popular: true,
  },
  pro: {
    name: "Pro",
    monthly: 599,
    yearly: 4999,
    features: ["Unlimited resumes", "Unlimited job searches", "ATS scoring", "Unlimited AI generation", "Priority support"],
  },
};

const COMPARISON = [
  ["Resume limit", "2", "10", "Unlimited"],
  ["Job searches/day", "5", "50", "Unlimited"],
  ["ATS scoring", "No", "Yes", "Yes"],
  ["AI generations", "No", "5/month", "Unlimited"],
  ["Priority support", "No", "No", "Yes"],
];

export default function SubscriptionPage() {
  const [billingCycle, setBillingCycle] = useState("monthly");
  const [currentPlan] = useState("free");
  const [upgradePlan, setUpgradePlan] = useState("");

  const selectedPrice = useMemo(
    () => (plan) => (billingCycle === "monthly" ? plan.monthly : plan.yearly),
    [billingCycle],
  );

  return (
    <>
      <div className="space-y-6">
        <section className="surface-card">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Choose your plan</h2>
              <p className="mt-1 text-sm text-gray-500">Upgrade anytime to unlock higher limits and AI features.</p>
            </div>

            <div className="rounded-lg border border-gray-200 bg-gray-50 p-1">
              <button
                type="button"
                className={`rounded-md px-4 py-2 text-sm font-semibold ${billingCycle === "monthly" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500"}`}
                onClick={() => setBillingCycle("monthly")}
              >
                Monthly
              </button>
              <button
                type="button"
                className={`rounded-md px-4 py-2 text-sm font-semibold ${billingCycle === "yearly" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500"}`}
                onClick={() => setBillingCycle("yearly")}
              >
                Yearly (save more)
              </button>
            </div>
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-3">
          {Object.entries(PLANS).map(([key, plan]) => {
            const price = selectedPrice(plan);
            const isCurrent = key === currentPlan;
            return (
              <article
                key={key}
                className={`surface-card relative ${plan.popular ? "border-teal-300 ring-2 ring-teal-100" : ""}`}
              >
                {plan.popular ? (
                  <span className="absolute right-4 top-4 rounded-full bg-teal-100 px-2.5 py-1 text-xs font-semibold text-teal-700">
                    Popular
                  </span>
                ) : null}

                <h3 className="text-xl font-bold text-gray-900">{plan.name}</h3>
                <p className="mt-2 text-3xl font-bold text-gray-900">
                  {"\u20B9"}
                  {price}
                </p>
                <p className="text-sm text-gray-500">/{billingCycle === "monthly" ? "month" : "year"}</p>

                <ul className="mt-4 space-y-2">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2 text-sm text-gray-700">
                      <Check className="h-4 w-4 text-emerald-500" />
                      {feature}
                    </li>
                  ))}
                </ul>

                {isCurrent ? (
                  <button type="button" className="mt-6 w-full rounded-lg bg-gray-100 px-4 py-2.5 text-sm font-semibold text-gray-500" disabled>
                    Current Plan
                  </button>
                ) : (
                  <button type="button" className="btn-primary mt-6 w-full" onClick={() => setUpgradePlan(key)}>
                    <Crown className="mr-2 h-4 w-4" />
                    Upgrade Now
                  </button>
                )}
              </article>
            );
          })}
        </section>

        <section className="surface-card overflow-hidden">
          <h3 className="mb-4 text-lg font-semibold text-gray-900">Feature comparison</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-600">
                  <th className="px-3 py-2 font-semibold">Feature</th>
                  <th className="px-3 py-2 font-semibold">Free</th>
                  <th className="px-3 py-2 font-semibold">Basic</th>
                  <th className="px-3 py-2 font-semibold">Pro</th>
                </tr>
              </thead>
              <tbody>
                {COMPARISON.map((row) => (
                  <tr key={row[0]} className="border-b border-gray-100 last:border-0">
                    <td className="px-3 py-2 font-medium text-gray-700">{row[0]}</td>
                    <td className="px-3 py-2 text-gray-600">{row[1]}</td>
                    <td className="px-3 py-2 text-gray-600">{row[2]}</td>
                    <td className="px-3 py-2 text-gray-600">{row[3]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <ConfirmModal
        isOpen={Boolean(upgradePlan)}
        title="Razorpay Payment"
        message={
          upgradePlan
            ? `Proceed to Razorpay for ${PLANS[upgradePlan].name} plan (\u20B9${selectedPrice(PLANS[upgradePlan])}/${
                billingCycle === "monthly" ? "month" : "year"
              }).`
            : ""
        }
        confirmText="Proceed to Pay"
        onCancel={() => setUpgradePlan("")}
        onConfirm={() => setUpgradePlan("")}
      />
    </>
  );
}
