import '../static/account.css'
import '../static/global.css'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import FrontendGeneration from './components/FrontendGeneration'
import FrontendOverview from './components/FrontendOverview'
import FrontendResults from './components/FrontendResults'
import BackendGeneration from './components/BackendGeneration'
import BackendOverview from './components/BackendOverview'
import BackendResults from './components/BackendResults'
import '../static/frontOver.css'

export default function Account(){
    const [isListVisible, setIsListVisible] = useState(false)
    const [projects, setProjects] = useState([])
    const [cards, setCards] = useState([
        { id: 1, type: 'new' },
        { id: 2, type: 'empty' },
        { id: 3, type: 'empty' },
        { id: 4, type: 'empty' },
        { id: 5, type: 'empty' },
        { id: 6, type: 'empty' }
    ])
    const [activeProjectMenu, setActiveProjectMenu] = useState(null)
    const [activeButtons, setActiveButtons] = useState({
        frontend: false,
        backend: false,
        overview: false,
        results: false,
        generation: false
    })
    
    const [activeTab, setActiveTab] = useState(null)
    const [activeSubTab, setActiveSubTab] = useState('overview')
    const [selectedProject, setSelectedProject] = useState(null) // Добавляем состояние для выбранного проекта

    const toggleList = () => {
        setIsListVisible(!isListVisible)
    }

    const toggleProjectMenu = (projectId) => {
        setActiveProjectMenu(activeProjectMenu === projectId ? null : projectId)
    }

    const handleBackButton = () => {
        setActiveTab(null)
        setActiveSubTab('overview')
        setActiveProjectMenu(null)
        setSelectedProject(null) // Сбрасываем выбранный проект
        setActiveButtons({
            frontend: false,
            backend: false,
            overview: false,
            results: false,
            generation: false
        })
    }

    const handleButtonClick = (buttonType, project) => {
        setActiveButtons(prev => {
            const newState = {...prev};
            
            if (buttonType === 'frontend' || buttonType === 'backend') {
                newState.frontend = false;
                newState.backend = false;
                
                setActiveTab(buttonType);
                setActiveSubTab('overview');
                setSelectedProject(project); // Сохраняем выбранный проект
                newState.overview = true;
                newState.results = false;
                newState.generation = false;
            }
            
            if (buttonType === 'overview' || buttonType === 'results' || buttonType === 'generation') {
                newState.overview = false;
                newState.results = false;
                newState.generation = false;
                setActiveSubTab(buttonType);
            }
            
            newState[buttonType] = true;
            
            return newState;
        });
    };

    const addProject = (cardId) => {
        const projectName = `Проект ${projects.length + 1}`
        const randomProgress = Math.floor(Math.random() * 80) + 10
        
        const newProject = {
            name: projectName,
            progress: randomProgress,
            id: Date.now(),
            // Добавляем дополнительные данные для тестов
            testPercentage: randomProgress,
            indicators: [
                { name: 'Auth', status: 'completed' },
                { name: 'Market', status: 'in-progress' },
                { name: 'Tickets', status: 'not-started' }
            ]
        }
        
        setProjects([...projects, newProject])
        
        const updatedCards = cards.map(card => {
            if (card.id === cardId) {
                return { 
                    ...card, 
                    type: 'grid', 
                    name: projectName,
                    progress: randomProgress,
                    projectData: newProject // Сохраняем данные проекта в карточке
                }
            }
            return card
        })
        
        const nextEmptyCard = updatedCards.find(card => card.type === 'empty')
        if (nextEmptyCard) {
            const finalCards = updatedCards.map(card => 
                card.id === nextEmptyCard.id ? { ...card, type: 'new' } : card
            )
            setCards(finalCards)
        } else {
            setCards(updatedCards)
        }
    }

    const getGradientStyle = (progress) => {
        return {
            background: `linear-gradient(to right, #0258d8 ${progress}%, white 100%)`
        }
    }

    const renderActiveContent = () => {
        if (!activeTab || !selectedProject) return null;

        // Находим актуальные данные проекта
        const currentProject = projects.find(p => p.id === selectedProject.id) || selectedProject;

        switch (activeSubTab) {
            case 'overview':
                return activeTab === 'frontend' ? 
                    <FrontendOverview project={currentProject} /> : 
                    <BackendOverview project={currentProject} />;
            case 'results':
                return activeTab === 'frontend' ? 
                    <FrontendResults project={currentProject} /> : 
                    <BackendResults project={currentProject} />;
            case 'generation':
                return activeTab === 'frontend' ? 
                    <FrontendGeneration project={currentProject} /> : 
                    <BackendGeneration project={currentProject} />;
            default:
                return activeTab === 'frontend' ? 
                    <FrontendOverview project={currentProject} /> : 
                    <BackendOverview project={currentProject} />;
        }
    }

    const renderCard = (card) => {
        switch (card.type) {
            case 'grid':
                return (
                    <div 
                        className='card card-grid' 
                        key={card.id}
                        style={getGradientStyle(card.progress)}
                    >
                        <div id='card-name-div'>
                            <p id='card-name'>{card.name}</p>
                            <p id='progress-text'>{card.progress}%</p>
                        </div>
                        <div id='bottom-row'>
                            <Link to='/' id='gear'/>
                            <div 
                                id='indicator' 
                                className={card.progress === 100 ? 'completed' : 'in-progress'}
                            ></div>
                        </div>
                    </div>
                )
            case 'new':
                return (
                    <div className='card new-card' key={card.id}>
                        <button className="add-project" onClick={() => addProject(card.id)}>
                            <p className='plus'>+</p>
                        </button>
                    </div>
                )
            case 'empty':
                return <div className='card' key={card.id}></div>
            default:
                return <div className='card' key={card.id}></div>
        }
    }

    return(
        <div id="travoman">
            <div className='homelink'><Link to='/' className='home'>Главная</Link></div>
            <div id="account">
                <aside id="accountpanel">
                    <div id="user">
                        <div id='ava'></div>
                        <div id='user-name'></div>
                    </div>
                    {activeTab && (
                        <div id='backup-button-div'>
                            <button id='backup-button' onClick={handleBackButton}>
                                Назад
                            </button>
                        </div>
                    )}
                    <div id='projects'>
                        <button id='buttproj' onClick={toggleList}>
                            <p id='butt-sign'>Проекты</p>
                        </button>
                        <ul id='list' className={isListVisible ? 'visible' : 'hidden'}>
                            {projects.map((project) => (
                                <li key={project.id} className="project-item">
                                    <span 
                                        className="project-name"
                                        onClick={() => toggleProjectMenu(project.id)}
                                    >
                                        {project.name} - {project.progress}%
                                    </span>
                                    {activeProjectMenu === project.id && (
                                        <div className="project-menu">
                                            <button 
                                                id='Front' 
                                                className={`stbutt ${activeButtons.frontend ? 'active' : ''}`}
                                                onClick={() => handleButtonClick('frontend', project)}
                                            >
                                                Frontend
                                            </button>
                                            <button 
                                                id='Back' 
                                                className={`stbutt ${activeButtons.backend ? 'active' : ''}`}
                                                onClick={() => handleButtonClick('backend', project)}
                                            >
                                                Backend
                                            </button>
                                            <button 
                                                id='overview' 
                                                className={`ndbutt ${activeButtons.overview ? 'active' : ''}`}
                                                onClick={() => handleButtonClick('overview', project)}
                                            >
                                                Обзор
                                            </button>
                                            <button 
                                                id='results' 
                                                className={`ndbutt ${activeButtons.results ? 'active' : ''}`}
                                                onClick={() => handleButtonClick('results', project)}
                                            >
                                                Результаты
                                            </button>
                                            <button 
                                                id="gen" 
                                                className={`ndbutt ${activeButtons.generation ? 'active' : ''}`}
                                                onClick={() => handleButtonClick('generation', project)}
                                            >
                                                Генерация тестов
                                            </button>
                                        </div>
                                    )}
                                </li>
                            ))}
                        </ul>
                    </div>
                </aside>

                {!activeTab ? (
                    <>
                        <div className='cardsdiv' id='firstdiv'>
                            {cards.slice(0, 3).map(card => renderCard(card))}
                        </div>
                        <div className='cardsdiv' id='secdiv'>
                            {cards.slice(3, 6).map(card => renderCard(card))}
                        </div>
                    </>
                ) : (
                    <div className="tab-container">
                        {renderActiveContent()}
                    </div>
                )}
            </div>
        </div>
    )
}