import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import ThemeToggle from './components/ThemeToggle';
import Overview from './pages/Overview';
import Offers from './pages/Offers';
import Applications from './pages/Applications';
import Closed from './pages/Closed';
import Keywords from './pages/Keywords';
import JobTypes from './pages/JobTypes';
import ScrapeZones from './pages/ScrapeZones';
import Prefilter from './pages/Prefilter';
import Prompts from './pages/Prompts';
import Criteria from './pages/Criteria';
import Quotas from './pages/Quotas';
import Run from './pages/Run';
import Chat from './pages/Chat';
import Documentation from './pages/Documentation';
import ProfileMaster from './pages/ProfileMaster';

export default function App() {
  return (
    <BrowserRouter>
      <Sidebar />
      <ThemeToggle />
      <main className="main">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/offers" element={<Offers />} />
          <Route path="/applications" element={<Applications />} />
          <Route path="/closed" element={<Closed />} />
          <Route path="/keywords" element={<Keywords />} />
          <Route path="/job-types" element={<JobTypes />} />
          <Route path="/scrape-zones" element={<ScrapeZones />} />
          <Route path="/prefilter" element={<Prefilter />} />
          <Route path="/prompts" element={<Prompts />} />
          <Route path="/criteria" element={<Criteria />} />
          <Route path="/quotas" element={<Quotas />} />
          <Route path="/run" element={<Run />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/documentation" element={<Documentation />} />
          <Route path="/profile-master" element={<ProfileMaster />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
