import React, { useState } from 'react';
import {
  Phone, Microscope, FlaskConical, BookOpen, FileText,
  AlertTriangle, ChevronRight, ExternalLink
} from 'lucide-react';

// Parameter Table Component
const ParameterTable = ({ title, description, parameters }) => (
  <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
    <div className="px-5 py-4 border-b border-slate-100">
      <h4 className="font-semibold text-slate-800">{title}</h4>
      {description && <p className="text-sm text-slate-500 mt-1">{description}</p>}
    </div>
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-50">
            <th className="px-5 py-3 text-left font-medium text-slate-600">Intervention</th>
            <th className="px-5 py-3 text-left font-medium text-slate-600">Parameter</th>
            <th className="px-5 py-3 text-left font-medium text-slate-600">Baseline</th>
            <th className="px-5 py-3 text-left font-medium text-slate-600">With Intervention</th>
            <th className="px-5 py-3 text-left font-medium text-slate-600">Evidence Needed</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {parameters.map((param, i) => (
            <tr key={i} className="hover:bg-slate-50/50">
              <td className="px-5 py-3 text-slate-700">{param.intervention}</td>
              <td className="px-5 py-3">
                <code className="text-xs bg-slate-100 px-1.5 py-0.5 rounded text-slate-600 font-mono">
                  {param.parameter}
                </code>
              </td>
              <td className="px-5 py-3 text-slate-500 tabular-nums">{param.baseline}</td>
              <td className="px-5 py-3 text-emerald-600 font-medium tabular-nums">{param.withIntervention}</td>
              <td className="px-5 py-3 text-slate-500 text-xs">{param.evidence}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

// Section Component
const Section = ({ id, title, children }) => (
  <section id={id} className="scroll-mt-24">
    <h3 className="text-xl font-semibold text-slate-800 mb-4 pb-2 border-b border-slate-200">{title}</h3>
    {children}
  </section>
);

// Rationale Block
const Rationale = ({ children }) => (
  <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 mb-6">
    <div className="flex items-start gap-3">
      <BookOpen className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
      <div className="text-sm text-blue-800 leading-relaxed">{children}</div>
    </div>
  </div>
);

// Speculation Warning
const SpeculationWarning = ({ level = 'medium', children }) => {
  const styles = {
    low: { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-800', icon: 'text-emerald-500', label: 'Near-term feasible' },
    medium: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-800', icon: 'text-amber-500', label: 'Requires R&D' },
    high: { bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-800', icon: 'text-purple-500', label: 'Highly speculative' },
  };
  const style = styles[level];

  return (
    <div className={`${style.bg} ${style.border} border rounded-lg p-4 mb-6`}>
      <div className="flex items-start gap-3">
        <AlertTriangle className={`w-5 h-5 ${style.icon} flex-shrink-0 mt-0.5`} />
        <div>
          <span className={`text-xs font-medium ${style.text} uppercase tracking-wide`}>{style.label}</span>
          <div className={`text-sm ${style.text} mt-1 leading-relaxed`}>{children}</div>
        </div>
      </div>
    </div>
  );
};

// Reference Link
const Reference = ({ href, children }) => (
  <a href={href} target="_blank" rel="noopener noreferrer"
     className="inline-flex items-center gap-1 text-blue-600 hover:underline text-sm">
    {children}
    <ExternalLink className="w-3 h-3" />
  </a>
);

// Figure with subfigures
const Figure = ({ children, caption, number }) => (
  <figure className="my-6">
    <div className="flex flex-col md:flex-row gap-4">
      {children}
    </div>
    {caption && (
      <figcaption className="mt-3 text-sm text-slate-600 text-center">
        <span className="font-medium">Figure {number}.</span> {caption}
      </figcaption>
    )}
  </figure>
);

// Subfigure component
const SubFigure = ({ src, alt, caption, citation }) => (
  <div className="flex-1 flex flex-col">
    <div className="bg-slate-50 border border-slate-200 rounded-lg p-2 flex items-center justify-center min-h-[200px]">
      <img
        src={src}
        alt={alt}
        className="max-w-full max-h-[280px] object-contain rounded"
      />
    </div>
    {caption && (
      <div className="mt-2 text-xs text-slate-500 text-center">
        {caption}
        {citation && (
          <>
            {' '}
            <a
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-500 hover:underline"
            >
              [{citation.label}]
            </a>
          </>
        )}
      </div>
    )}
  </div>
);

export default function InterventionsTab() {
  const [activeSection, setActiveSection] = useState('agents');

  return (
    <div className="h-full overflow-auto bg-slate-50">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-white/95 backdrop-blur-xl border-b border-slate-200 px-8 py-4">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center">
                <FileText className="w-5 h-5 text-slate-600" />
              </div>
              <div>
                <h2 className="text-lg font-medium text-slate-800">Intervention Mechanisms</h2>
                <p className="text-xs text-slate-500">Model parameters and evidence requirements</p>
              </div>
            </div>

            {/* Section Toggle */}
            <div className="flex items-center gap-1 bg-slate-100 rounded-xl p-1">
              <button
                onClick={() => setActiveSection('agents')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  activeSection === 'agents'
                    ? 'bg-white text-slate-800 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                <Phone className="w-4 h-4" />
                AI Agents
              </button>
              <button
                onClick={() => setActiveSection('labs')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  activeSection === 'labs'
                    ? 'bg-white text-slate-800 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                <Microscope className="w-4 h-4" />
                Distributed Diagnostics
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-5xl mx-auto px-8 py-8">
        {activeSection === 'agents' ? (
          <div className="space-y-8">
            {/* Introduction */}
            <Section id="agents-intro" title="Population-Scale AI Health Agents">
              <Rationale>
                <strong>Why this matters:</strong> Standard SEIR models assume fixed parameters for contact tracing
                efficacy, reporting rates, and compliance. In practice, these parameters are limited by human capacity
                constraints—health workers can only make so many calls per day, language barriers reduce comprehension,
                and follow-up compliance decays without sustained engagement. AI voice and text agents can operate at
                population scale with consistent quality, fundamentally changing what parameter values are achievable.
              </Rationale>

              <p className="text-slate-600 mb-6 leading-relaxed">
                This intervention explores how AI-powered phone and SMS agents could modify key epidemiological
                parameters in pandemic response models. We examine four primary mechanisms: contact tracing
                acceleration, sustained compliance support, symptom surveillance, and health information delivery.
              </p>
            </Section>

            {/* Contact Tracing */}
            <Section id="contact-tracing" title="1. Contact Tracing Parameters">
              <p className="text-slate-600 mb-4 leading-relaxed">
                Traditional contact tracing is limited by the number of trained interviewers and the time required
                per case. AI agents can conduct structured interviews in multiple languages simultaneously,
                dramatically reducing the time from case identification to contact notification.
              </p>

              <ParameterTable
                title="Contact Tracing Model Parameters"
                description="How AI agents modify standard contact tracing assumptions"
                parameters={[
                  {
                    intervention: 'Trace completion rate',
                    parameter: 'p_trace',
                    baseline: '0.3–0.5',
                    withIntervention: '0.7–0.9',
                    evidence: 'Pilot completion rates vs. manual tracing'
                  },
                  {
                    intervention: 'Time to first contact',
                    parameter: 'τ_contact',
                    baseline: '48–72h',
                    withIntervention: '1–4h',
                    evidence: 'Operational timestamps from call logs'
                  },
                  {
                    intervention: 'Contacts identified per case',
                    parameter: 'n_contacts',
                    baseline: '3–5',
                    withIntervention: '8–15',
                    evidence: 'Interview depth comparison studies'
                  },
                  {
                    intervention: 'Language coverage',
                    parameter: 'p_language',
                    baseline: '0.6–0.8',
                    withIntervention: '0.95+',
                    evidence: 'Comprehension testing across languages'
                  },
                ]}
              />

              <div className="mt-4 text-sm text-slate-500">
                <strong>Key assumption:</strong> AI agents can conduct structured epidemiological interviews
                with sufficient accuracy. This requires validation against human interviewer gold standards.
              </div>
            </Section>

            {/* Compliance */}
            <Section id="compliance" title="2. Quarantine & Isolation Compliance">
              <p className="text-slate-600 mb-4 leading-relaxed">
                Compliance with quarantine recommendations typically decays over time due to isolation fatigue,
                economic pressures, and lack of ongoing support. Regular AI check-ins can provide sustained
                engagement, mental health support, and practical assistance coordination.
              </p>

              <ParameterTable
                title="Compliance Decay Parameters"
                description="Modeling sustained engagement effects on isolation adherence"
                parameters={[
                  {
                    intervention: 'Initial compliance',
                    parameter: 'c(0)',
                    baseline: '0.7–0.8',
                    withIntervention: '0.85–0.95',
                    evidence: 'Day-1 adherence surveys'
                  },
                  {
                    intervention: 'Compliance half-life',
                    parameter: 't_half',
                    baseline: '5–7 days',
                    withIntervention: '12–18 days',
                    evidence: 'Longitudinal compliance tracking'
                  },
                  {
                    intervention: 'Day-14 compliance',
                    parameter: 'c(14)',
                    baseline: '0.25–0.35',
                    withIntervention: '0.55–0.70',
                    evidence: 'End-of-quarantine surveys'
                  },
                  {
                    intervention: 'Support utilization',
                    parameter: 'p_support',
                    baseline: '0.1–0.2',
                    withIntervention: '0.5–0.7',
                    evidence: 'Resource request logs'
                  },
                ]}
              />

              <div className="mt-4 p-4 bg-slate-100 rounded-lg">
                <div className="text-sm text-slate-600">
                  <strong>Modeling note:</strong> Standard models often assume constant compliance <code className="bg-white px-1 rounded">c</code>.
                  A more realistic approach uses exponential decay: <code className="bg-white px-1 rounded">c(t) = c(0) · e^(-λt)</code> where
                  AI intervention modifies both <code className="bg-white px-1 rounded">c(0)</code> and the decay rate <code className="bg-white px-1 rounded">λ</code>.
                </div>
              </div>
            </Section>

            {/* Symptom Reporting */}
            <Section id="symptom-reporting" title="3. Symptom Surveillance">
              <p className="text-slate-600 mb-4 leading-relaxed">
                Early case detection depends on individuals recognizing symptoms and seeking testing.
                Proactive daily symptom check-ins via AI agents can dramatically increase the fraction
                of symptomatic individuals who enter the healthcare system early.
              </p>

              <ParameterTable
                title="Symptom Reporting Parameters"
                description="Effects of proactive surveillance on case detection"
                parameters={[
                  {
                    intervention: 'Symptom reporting rate',
                    parameter: 'p_report',
                    baseline: '0.2–0.4',
                    withIntervention: '0.6–0.8',
                    evidence: 'Self-report vs. confirmed case matching'
                  },
                  {
                    intervention: 'Time from symptom to test',
                    parameter: 'τ_test',
                    baseline: '3–5 days',
                    withIntervention: '0.5–1.5 days',
                    evidence: 'Symptom onset to test date intervals'
                  },
                  {
                    intervention: 'Asymptomatic identification',
                    parameter: 'p_asymp_detect',
                    baseline: '0.05–0.15',
                    withIntervention: '0.20–0.35',
                    evidence: 'Contact-based testing yield'
                  },
                ]}
              />
            </Section>

            {/* Information Delivery */}
            <Section id="information" title="4. Health Information Delivery">
              <p className="text-slate-600 mb-4 leading-relaxed">
                Behavior change depends on accurate health information reaching populations. AI agents
                can deliver personalized, culturally-appropriate guidance and counter misinformation
                in real-time, affecting the behavioral parameters that drive transmission.
              </p>

              <ParameterTable
                title="Behavioral Parameters"
                description="Information effects on transmission-relevant behaviors"
                parameters={[
                  {
                    intervention: 'Protective behavior adoption',
                    parameter: 'p_protect',
                    baseline: '0.3–0.5',
                    withIntervention: '0.6–0.8',
                    evidence: 'Behavioral surveys, mobility data'
                  },
                  {
                    intervention: 'Misinformation prevalence',
                    parameter: 'p_misinfo',
                    baseline: '0.2–0.4',
                    withIntervention: '0.05–0.15',
                    evidence: 'Knowledge assessment surveys'
                  },
                  {
                    intervention: 'Vaccine acceptance',
                    parameter: 'p_vax_accept',
                    baseline: '0.5–0.7',
                    withIntervention: '0.7–0.85',
                    evidence: 'Vaccination uptake in pilot regions'
                  },
                ]}
              />
            </Section>

            {/* Summary */}
            <Section id="agents-summary" title="Aggregate Model Impact">
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-5">
                <p className="text-sm text-emerald-800 leading-relaxed mb-4">
                  When these parameter modifications are applied to the SEIR model used in this dashboard,
                  the combined effect produces the dramatic reductions shown in the simulation. The key
                  driver is the multiplicative effect of faster tracing, higher compliance, and earlier
                  case detection—each improvement amplifies the others.
                </p>
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div className="bg-white rounded-lg p-3 border border-emerald-100">
                    <div className="text-2xl font-bold text-emerald-600">R_eff</div>
                    <div className="text-xs text-slate-500">1.66 → 0.51</div>
                  </div>
                  <div className="bg-white rounded-lg p-3 border border-emerald-100">
                    <div className="text-2xl font-bold text-emerald-600">Peak ↓</div>
                    <div className="text-xs text-slate-500">99.8% reduction</div>
                  </div>
                  <div className="bg-white rounded-lg p-3 border border-emerald-100">
                    <div className="text-2xl font-bold text-emerald-600">Deaths ↓</div>
                    <div className="text-xs text-slate-500">~220K averted</div>
                  </div>
                </div>
              </div>
            </Section>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Introduction */}
            <Section id="labs-intro" title="Distributed Diagnostic Capacity">
              <Rationale>
                <strong>Why this matters:</strong> Testing capacity is a critical bottleneck in pandemic response.
                Centralized laboratories create transportation delays, backlogs during surges, and inequitable
                access for remote populations. Modular, containerized laboratories can be deployed to outbreak
                hotspots, reducing sample-to-result time and enabling the rapid testing that contact tracing
                and isolation strategies depend upon.
              </Rationale>

              <SpeculationWarning level="medium">
                Containerized BSL-2 diagnostic laboratories exist and are deployed by organizations like MSF.
                The speculation here is in the scale of deployment, AI-driven positioning, and integration
                with digital health systems. BSL-3+ and vaccine production remain highly speculative.
              </SpeculationWarning>

              <Figure
                number={1}
                caption="Left: GermFree Mobile BSL-2/3 laboratory currently deployed for outbreak response.
                         Right: Concept illustration of a future autonomous modular laboratory with integrated
                         renewable power, robotic sample handling, and AI-driven operations."
              >
                <SubFigure
                  src="/images/germfree-mobile-lab.webp"
                  alt="GermFree containerized mobile BSL-2/3 laboratory"
                  caption="(a) GermFree Mobile Laboratory"
                  citation={{
                    url: "https://www.medicalexpo.com/prod/germfree/product-108820-748517.html",
                    label: "Source"
                  }}
                />
                <SubFigure
                  src="/images/autonomous-lab-concept.png"
                  alt="Concept drawing of autonomous modular laboratory with solar panels, wind turbines, and robotic systems"
                  caption="(b) Autonomous Lab Concept (this work)"
                />
              </Figure>
            </Section>

            {/* Diagnostic Parameters */}
            <Section id="diagnostic-params" title="1. Diagnostic Capacity Parameters">
              <p className="text-slate-600 mb-4 leading-relaxed">
                Testing availability directly affects case detection rates and the feasibility of
                test-trace-isolate strategies. Distributed labs modify the accessibility and turnaround
                time parameters that constrain these interventions.
              </p>

              <ParameterTable
                title="Testing Capacity Parameters"
                description="How distributed diagnostics modify testing constraints"
                parameters={[
                  {
                    intervention: 'Distance to testing',
                    parameter: 'd_test',
                    baseline: '50–200 km',
                    withIntervention: '10–30 km',
                    evidence: 'GIS analysis of lab placement'
                  },
                  {
                    intervention: 'Sample-to-result time',
                    parameter: 'τ_result',
                    baseline: '2–5 days',
                    withIntervention: '4–12 hours',
                    evidence: 'Lab information system timestamps'
                  },
                  {
                    intervention: 'Tests per 1000 per day',
                    parameter: 'r_test',
                    baseline: '0.5–2',
                    withIntervention: '5–15',
                    evidence: 'Throughput during outbreak response'
                  },
                  {
                    intervention: 'Surge capacity factor',
                    parameter: 'k_surge',
                    baseline: '1.5–2x',
                    withIntervention: '5–10x',
                    evidence: 'Redeployment time and logistics'
                  },
                ]}
              />
            </Section>

            {/* Sequencing */}
            <Section id="sequencing" title="2. Genomic Surveillance">
              <p className="text-slate-600 mb-4 leading-relaxed">
                Variant detection and phylogenetic tracking require sequencing capacity. Distributed
                labs with portable sequencing (e.g., Oxford Nanopore) can enable real-time genomic
                surveillance at the outbreak edge rather than centralized retrospective analysis.
              </p>

              <ParameterTable
                title="Sequencing Parameters"
                description="Genomic surveillance capacity modifications"
                parameters={[
                  {
                    intervention: 'Sequencing coverage',
                    parameter: 'p_seq',
                    baseline: '0.01–0.05',
                    withIntervention: '0.10–0.25',
                    evidence: 'Sequences submitted to databases'
                  },
                  {
                    intervention: 'Time to variant detection',
                    parameter: 'τ_variant',
                    baseline: '2–4 weeks',
                    withIntervention: '3–7 days',
                    evidence: 'First local detection vs. global reports'
                  },
                  {
                    intervention: 'Cluster identification',
                    parameter: 'p_cluster',
                    baseline: '0.2–0.4',
                    withIntervention: '0.6–0.8',
                    evidence: 'Phylogenetic linkage success rate'
                  },
                ]}
              />
            </Section>

            {/* Sample Logistics */}
            <Section id="logistics" title="3. Sample Collection Networks">
              <p className="text-slate-600 mb-4 leading-relaxed">
                Even with distributed labs, sample collection remains a constraint. Mobile collection
                units, community health worker networks, and potentially drone logistics can extend
                the effective reach of diagnostic capacity.
              </p>

              <ParameterTable
                title="Sample Logistics Parameters"
                description="Collection network effects on testing access"
                parameters={[
                  {
                    intervention: 'Collection point density',
                    parameter: 'ρ_collect',
                    baseline: '1 per 50K pop',
                    withIntervention: '1 per 5K pop',
                    evidence: 'Mapping of collection infrastructure'
                  },
                  {
                    intervention: 'Sample viability window',
                    parameter: 't_viable',
                    baseline: '24–48h (cold)',
                    withIntervention: '4–8h (ambient)',
                    evidence: 'Sample quality metrics at lab receipt'
                  },
                  {
                    intervention: 'Rural access rate',
                    parameter: 'p_rural',
                    baseline: '0.2–0.4',
                    withIntervention: '0.6–0.8',
                    evidence: 'Testing rates by population density'
                  },
                ]}
              />
            </Section>

            {/* Speculative: Vaccines */}
            <Section id="vaccines" title="4. Distributed Vaccine Production (Speculative)">
              <SpeculationWarning level="high">
                Distributed vaccine manufacturing is a long-term research direction, not a near-term
                intervention. Current mRNA platforms require specialized facilities, cold chains, and
                regulatory frameworks that do not support rapid distributed deployment. This section
                explores what parameter changes <em>would</em> be relevant if such technology matured.
              </SpeculationWarning>

              <p className="text-slate-600 mb-4 leading-relaxed">
                The ultimate bottleneck in pandemic response is often vaccine availability. If modular
                vaccine manufacturing became feasible, it would modify the fundamental constraints on
                how quickly population immunity can be achieved.
              </p>

              <ParameterTable
                title="Hypothetical Vaccine Production Parameters"
                description="If distributed manufacturing were achievable (speculative)"
                parameters={[
                  {
                    intervention: 'Sequence to first dose',
                    parameter: 'τ_vax_dev',
                    baseline: '12–18 months',
                    withIntervention: '2–4 months',
                    evidence: 'Would require clinical trial reform'
                  },
                  {
                    intervention: 'Production scale-up',
                    parameter: 't_scale',
                    baseline: '6–12 months',
                    withIntervention: '1–2 months',
                    evidence: 'Manufacturing capacity studies'
                  },
                  {
                    intervention: 'Doses per day (regional)',
                    parameter: 'r_vax',
                    baseline: '10K–50K',
                    withIntervention: '500K–2M',
                    evidence: 'Distributed vs. centralized throughput'
                  },
                ]}
              />

              <div className="mt-4 p-4 bg-purple-50 border border-purple-200 rounded-lg">
                <div className="text-sm text-purple-800">
                  <strong>Research priorities:</strong> Before distributed vaccine production becomes
                  relevant, significant advances are needed in: (1) platform standardization, (2)
                  portable quality assurance, (3) regulatory harmonization, and (4) cold chain
                  independence. Current efforts should focus on diagnostics and therapeutics.
                </div>
              </div>
            </Section>

            {/* Evidence Framework */}
            <Section id="evidence" title="Evidence Requirements">
              <div className="bg-slate-100 rounded-lg p-5">
                <p className="text-sm text-slate-700 mb-4">
                  For any parameter modification to be credible in policy models, evidence must be
                  collected at multiple levels:
                </p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-white rounded-lg p-4 border border-slate-200">
                    <div className="font-medium text-slate-800 mb-2">Pilot Studies</div>
                    <ul className="text-xs text-slate-600 space-y-1">
                      <li>• Controlled deployment in 2-3 regions</li>
                      <li>• Pre/post comparison with matched controls</li>
                      <li>• Operational metrics (timestamps, completion rates)</li>
                    </ul>
                  </div>
                  <div className="bg-white rounded-lg p-4 border border-slate-200">
                    <div className="font-medium text-slate-800 mb-2">Validation Studies</div>
                    <ul className="text-xs text-slate-600 space-y-1">
                      <li>• AI vs. human interviewer comparison</li>
                      <li>• Accuracy of symptom assessment</li>
                      <li>• User comprehension and trust metrics</li>
                    </ul>
                  </div>
                  <div className="bg-white rounded-lg p-4 border border-slate-200">
                    <div className="font-medium text-slate-800 mb-2">Outcome Studies</div>
                    <ul className="text-xs text-slate-600 space-y-1">
                      <li>• Transmission reduction in intervention areas</li>
                      <li>• Healthcare utilization patterns</li>
                      <li>• Cost-effectiveness analysis</li>
                    </ul>
                  </div>
                </div>
              </div>
            </Section>
          </div>
        )}
      </div>
    </div>
  );
}
