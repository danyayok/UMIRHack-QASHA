import '../static/account.css'
import '../static/global.css'
import { Link } from 'react-router-dom'
import { useState, useEffect, useRef } from 'react'
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
        { id: 1, type: 'new' }
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
    const [selectedProject, setSelectedProject] = useState(null)
    const [isProfileModalOpen, setIsProfileModalOpen] = useState(false)
    
    // Состояния для данных профиля
    const [profileData, setProfileData] = useState({
        login: 'GermanGering1',
        email: 'german@example.com',
        password: ''
    })
    
    const [initialProfileData, setInitialProfileData] = useState({
        login: 'GermanGering1',
        email: 'german@example.com',
        password: ''
    })
    
    const [hasChanges, setHasChanges] = useState(false)
    const [avatar, setAvatar] = useState(null)
    const cardsContainerRef = useRef(null)

    useEffect(() => {
        const changesExist = 
            profileData.login !== initialProfileData.login ||
            profileData.email !== initialProfileData.email ||
            profileData.password !== initialProfileData.password;
        
        setHasChanges(changesExist);
    }, [profileData, initialProfileData]);

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
        setSelectedProject(null)
        setActiveButtons({
            frontend: false,
            backend: false,
            overview: false,
            results: false,
            generation: false
        })
    }

    const openProfileModal = () => {
        setInitialProfileData(profileData);
        setHasChanges(false);
        setIsProfileModalOpen(true);
    }

    const closeProfileModal = () => {
        if (hasChanges) {
            const confirmClose = window.confirm('У вас есть несохраненные изменения. Вы уверены, что хотите закрыть?');
            if (!confirmClose) return;
        }

        if (hasChanges) {
            setProfileData(initialProfileData);
        }
        setHasChanges(false);
        setIsProfileModalOpen(false);
    }

    const handleInputChange = (field, value) => {
        setProfileData(prev => ({
            ...prev,
            [field]: value
        }));
    }

    const handleSaveChanges = () => {
        if (hasChanges) {
            console.log('Сохранение данных:', profileData);
            
            setInitialProfileData(profileData);
            setHasChanges(false);
            setIsProfileModalOpen(false);
        } else {
            closeProfileModal();
        }
    }

    const handleAvatarChange = (event) => {
        const file = event.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                setAvatar(e.target.result);
            };
            reader.readAsDataURL(file);
        }
    }

    const handleButtonClick = (buttonType, project) => {
        setActiveButtons(prev => {
            const newState = {...prev};
            
            if (buttonType === 'frontend' || buttonType === 'backend') {
                newState.frontend = false;
                newState.backend = false;
                
                setActiveTab(buttonType);
                setActiveSubTab('overview');
                setSelectedProject(project);
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
        // Проверяем лимит в 100 проектов
        if (projects.length >= 100) {
            alert('Достигнут максимальный лимит проектов (100)');
            return;
        }

        const projectName = `Проект ${projects.length + 1}`
        const randomProgress = Math.floor(Math.random() * 80) + 10
        
        const newProject = {
            name: projectName,
            progress: randomProgress,
            id: Date.now(),
            testPercentage: randomProgress,
            indicators: [
                { name: 'Auth', status: 'completed' },
                { name: 'Market', status: 'in-progress' },
                { name: 'Tickets', status: 'not-started' }
            ]
        }
        
        setProjects([...projects, newProject])
        
        // Обновляем карточки: заменяем новую карточку на проект и добавляем следующую новую
        const updatedCards = cards.map(card => {
            if (card.id === cardId) {
                return { 
                    ...card, 
                    type: 'grid', 
                    name: projectName,
                    progress: randomProgress,
                    projectData: newProject
                }
            }
            return card
        })
        
        // Добавляем новую карточку "добавить проект" в конец, если не достигли лимита
        if (projects.length < 99) { // 99 потому что мы только что добавили один проект
            updatedCards.push({ 
                id: Date.now() + 1, // Уникальный ID
                type: 'new' 
            })
        }
        
        setCards(updatedCards)

        // Прокручиваем к новой карточке
        setTimeout(() => {
            if (cardsContainerRef.current) {
                cardsContainerRef.current.scrollTop = cardsContainerRef.current.scrollHeight;
            }
        }, 100);
    }

    const getGradientStyle = (progress) => {
        if (progress < 25) {
            return {
                backgroundColor: '#ff6b6b'
            }
        } else if (progress < 75) {
            return {
                backgroundColor: '#ffd93d'
            }
        } else if (progress < 100) {
            return {
                backgroundColor: '#6bcf7f'
            }
        } else {
            return {
                backgroundColor: '#4caf50'
            }
        }
    }

    const renderActiveContent = () => {
        if (!activeTab || !selectedProject) return null;

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
                            <button id='gear'></button>
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
                return <div className='card empty-card' key={card.id}></div>
            default:
                return <div className='card empty-card' key={card.id}></div>
        }
    }

    // Функция для группировки карточек по рядам (по 3 в ряду)
    const groupCardsIntoRows = (cards) => {
        const rows = [];
        for (let i = 0; i < cards.length; i += 3) {
            rows.push(cards.slice(i, i + 3));
        }
        return rows;
    }

    const cardRows = groupCardsIntoRows(cards);

    return(
        <div id="travoman">
            <div id="account">

                {isProfileModalOpen && (
                    <div className="modal-overlay" onClick={closeProfileModal}>
                        <div id='profile-settings-div' onClick={(e) => e.stopPropagation()}>
                            <div 
                                id='avatar' 
                                style={avatar ? { backgroundImage: `url(${avatar})`, backgroundSize: 'cover' } : {}}
                            ></div>

                            <div id='inputs-div'>
                                <div className="account-input-container">
                                    <input 
                                        type="text" 
                                        id='login-input'
                                        value={profileData.login}
                                        onChange={(e) => handleInputChange('login', e.target.value)}
                                        required
                                    />
                                    <label htmlFor="login-input">Логин</label>
                                </div>
                                <div className="account-input-container">
                                    <input 
                                        type="text" 
                                        id='email-input'
                                        value={profileData.email}
                                        onChange={(e) => handleInputChange('email', e.target.value)}
                                        required
                                    />
                                    <label htmlFor="email-input">Почта</label>
                                </div>
                                <div className="account-input-container">
                                    <input 
                                        type="text" 
                                        id='pass-input'
                                        value={profileData.password}
                                        onChange={(e) => handleInputChange('password', e.target.value)}
                                        required
                                    />
                                    <label htmlFor="pass-input">Пароль</label>
                                </div>
                            </div>
                            <input
                                type="file"
                                id="avatar-input"
                                accept="image/*"
                                style={{ display: 'none' }}
                                onChange={handleAvatarChange}
                            />
                            <button 
                                id='change-avatar-button' 
                                onClick={() => document.getElementById('avatar-input').click()}
                            >
                                Сменить фото
                            </button>
                            <button 
                                id='save-changes-button' 
                                onClick={handleSaveChanges}
                                className={hasChanges ? 'has-changes' : ''}
                            >
                                {hasChanges ? 'Сохранить изменения' : 'Назад'}
                            </button>
                        </div>
                    </div>
                )}

                <aside id="accountpanel">
                    <div id="account-div">
                        <Link to="/" id="account-logo-link">
                            <div id='accountt'></div>
                            <span id='account-text'>Qasha</span>
                        </Link>
                    </div>
                    <div id="user" onClick={openProfileModal}>
                        <div 
                            id='ava' 
                            style={avatar ? { backgroundImage: `url(${avatar})`, backgroundSize: 'cover' } : {}}
                        ></div>
                        <div id='user-name-div'>
                            <p id='user-name'>{profileData.login}</p>
                        </div>
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
                    <div className='cards-container' ref={cardsContainerRef}>
                        {cardRows.map((row, rowIndex) => (
                            <div key={rowIndex} className='cards-grid'>
                                {row.map(card => renderCard(card))}
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="tab-container">
                        {renderActiveContent()}
                    </div>
                )}
            </div>
        </div>
    )
}